from typing import Dict, List, Tuple, Optional
import h5py
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from pyproj import CRS, Transformer
import logging
import os
import boto3
import concurrent.futures
import time
from botocore.config import Config
from osgeo import gdal
import s3fs
import json
from pathlib import Path
import shutil
from datetime import datetime  # Add this import
# from utils.metadata_handler import MetadataHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class L1CProcessor:
    def __init__(self, input_path: str, output_bucket: str, max_workers: int = 5):
        print(f"Initializing L1C processor for {input_path}")
        
        # Store the original input path
        self.input_path = input_path
        
        # Parse input path properly
        if input_path.startswith('s3://'):
            # Handle S3 paths
            path_parts = input_path[5:].split('/', 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid S3 path format: {input_path}. Expected format: s3://bucket/key")
            self.input_bucket = path_parts[0]
            self.input_key = path_parts[1]
        else:
            # Handle local file paths
            if not os.path.exists(input_path):
                raise ValueError(f"Local file not found: {input_path}")
            self.input_bucket = None
            self.input_key = os.path.basename(input_path)
            
        self.output_bucket = output_bucket
        self.max_workers = max_workers
        self.start_time = time.time()

        print(f"Input bucket: {self.input_bucket}")
        print(f"Input key: {self.input_key}")
        print(f"Output bucket: {self.output_bucket}")
        
        # Extract filename and setup paths
        self.filename = os.path.splitext(os.path.basename(input_path))[0]
        self.region = os.environ.get('AWS_DEFAULT_REGION', 'ap-south-1')
        self.temp_dir = '/tmp/processing'
        os.makedirs(self.temp_dir, exist_ok=True)
        print(f"Created temp directory: {self.temp_dir}")
        
        # Initialize AWS clients
        print("Initializing AWS clients...")
        self._init_aws_clients()
        
        # Download file locally
        self.local_path = os.path.join(self.temp_dir, self.input_key)
        print(f"Will use local file at: {self.local_path}")
        self._download_file()

        # Initialize projection parameters
        self.proj_params = {
            'proj': 'merc',
            'lon_0': 77.25,
            'lat_ts': 17.75,
            'x_0': 0,
            'y_0': 0,
            'a': 6378137,
            'b': 6356752.3142,
            'units': 'm'
        }
        
        # Initialize geographic bounds
        self.bounds = {
            'left': 44.5,
            'right': 110.0,
            'bottom': -10.0,
            'top': 45.5
        }
        
        print("Initialized projection parameters and bounds")
        # self.metadata_handler = MetadataHandler(region=self.region)

    def _init_aws_clients(self):
        """Initialize AWS clients"""
        try:
            print("Setting up S3 filesystem...")
            self.fs = s3fs.S3FileSystem(
                key=os.environ.get('AWS_ACCESS_KEY_ID'),
                secret=os.environ.get('AWS_SECRET_ACCESS_KEY'),
                client_kwargs={'region_name': self.region}
            )
            
            print("Configuring S3 client...")
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                config=Config(
                    max_pool_connections=50,
                    retries={'max_attempts': 3},
                    connect_timeout=60,
                    read_timeout=60
                )
            )
            print("AWS clients initialized successfully")
        except Exception as e:
            print(f"Failed to initialize AWS clients: {str(e)}")
            raise

    def _download_file(self):
        """Download the input file to local storage"""
        print(f"\n=== Downloading File ===")
        try:
            if self.input_bucket:
                print(f"Source: s3://{self.input_bucket}/{self.input_key}")
                print(f"Destination: {self.local_path}")
                self.s3_client.download_file(
                    self.input_bucket,
                    self.input_key,
                    self.local_path
                )
            else:
                # If it's a local file, just copy it
                shutil.copy2(self.input_path, self.local_path)
            print("Download/copy completed successfully")
            
        except Exception as e:
            print(f"Download/copy failed: {str(e)}")
            raise

    def convert_to_cog(self, input_tif: str, output_tif: str) -> bool:
        """Convert a GeoTIFF to Cloud Optimized GeoTIFF with LZW compression"""
        try:
            print(f"\n=== Converting to COG: {os.path.basename(input_tif)} ===")
            cog_options = gdal.TranslateOptions(
                format='GTiff',
                creationOptions=[
                    'COMPRESS=LZW',
                    'TILED=YES',
                    'COPY_SRC_OVERVIEWS=YES',
                    'BIGTIFF=YES',
                    'RESAMPLING=NEAREST',
                    'BLOCKXSIZE=512',
                    'BLOCKYSIZE=512'
                ]
            )
            gdal.Translate(output_tif, input_tif, options=cog_options)
            os.remove(input_tif)  # Remove original TIFF after conversion
            return True
        except Exception as e:
            print(f"ERROR in COG conversion: {str(e)}")
            return False

    def reproject_to_epsg3857(self, input_tif: str, output_tif: str) -> None:
        """Reproject a GeoTIFF to EPSG:3857"""
        warp_options = gdal.WarpOptions(
            dstSRS='EPSG:3857',
            format='GTiff',
            creationOptions=[
                'COMPRESS=LZW',
                'TILED=YES',
                'COPY_SRC_OVERVIEWS=YES',
                'BIGTIFF=YES',
                'RESAMPLING=NEAREST',
                'BLOCKXSIZE=512',
                'BLOCKYSIZE=512'
            ]
        )
        gdal.Warp(output_tif, input_tif, options=warp_options)
        os.remove(input_tif)  # Remove original TIFF after reprojection

    def process_single_band(self, key: str, data: np.ndarray, h5f, scale_factor: float, add_offset: float) -> Optional[str]:
        """Process a single band and upload it to S3"""
        print(f"\n=== Processing Band: {key} ===")
        
        temp_tif = f"/tmp/{key}_temp.tif"
        temp_reprojected_tif = f"/tmp/{key}_reprojected_temp.tif"
        final_cog = f"/tmp/{key}_cog.tif"
        s3_key = f"{self.filename}/{key}_cog.tif"

        try:
            # Data preparation
            data = data * scale_factor + add_offset
            print(f"Processed data shape: {data.shape}")
            
            # Get coordinates for transform
            crs = CRS.from_dict(self.proj_params)
            transformer = Transformer.from_crs(
                CRS.from_epsg(4326),
                crs,
                always_xy=True
            )
            
            left, bottom = transformer.transform(self.bounds['left'], self.bounds['bottom'])
            right, top = transformer.transform(self.bounds['right'], self.bounds['top'])
            
            transform = from_bounds(
                left, bottom, right, top,
                data.shape[1], data.shape[0]
            )
            
            # Write temporary GeoTIFF
            with rasterio.open(
                temp_tif,
                'w',
                driver='GTiff',
                height=data.shape[0],
                width=data.shape[1],
                count=1,
                dtype=data.dtype,
                crs=crs.to_wkt(),
                transform=transform,
            ) as dst:
                dst.write(data, 1)
                # Add metadata from HDF5 attributes
                dst.update_tags(**{
                    'WAVELENGTH': h5f[key].attrs.get(f'{key}_central_wavelength', ''),
                    'UNITS': h5f[key].attrs.get(f'{key}_RADIANCE_units', ''),
                    'DATETIME': datetime.now().strftime("%Y:%m:%d %H:%M:%S")
                })
            
            # Reproject to EPSG:3857
            self.reproject_to_epsg3857(temp_tif, temp_reprojected_tif)

            # Convert to COG and upload
            if not self.convert_to_cog(temp_reprojected_tif, final_cog):
                raise Exception(f"Failed to convert {key} to COG format")

            # Upload to S3
            self.s3_client.upload_file(
                final_cog,
                self.output_bucket,
                s3_key,
                ExtraArgs={
                    'ACL': 'bucket-owner-full-control',
                    'ContentType': 'image/tiff'
                }
            )
            print(f"Successfully uploaded: {s3_key}")
            return s3_key

        except Exception as e:
            print(f"ERROR processing band {key}: {str(e)}")
            return None
        finally:
            # Cleanup
            for file in [temp_tif, temp_reprojected_tif, final_cog]:
                if os.path.exists(file):
                    os.remove(file)

    def process(self) -> Dict[str, str]:
        """Main processing pipeline"""
        print("\n=== Starting L1C Processing Pipeline ===")
        results = {}
        
        BASE_IMAGES = ['IMG_MIR', 'IMG_SWIR', 'IMG_TIR1', 'IMG_TIR2', 'IMG_VIS', 'IMG_WV']
        print(f"Will process bands: {', '.join(BASE_IMAGES)}")
        
        try:
            print("\nOpening HDF5 file...")
            with h5py.File(self.local_path, 'r') as h5f:
                for key in BASE_IMAGES:
                    if key not in h5f:
                        print(f"Warning: Band {key} not found in file")
                        continue

                    print(f"\nProcessing band: {key}")
                    data = h5f[key][:]
                    data = np.squeeze(data)
                    
                    if len(data.shape) != 2:
                        print(f"Warning: Band {key} has unexpected shape {data.shape}")
                        continue

                    scale_factor = h5f[key].attrs.get(f'{key}_lab_radiance_scale_factor', 1.0)
                    add_offset = h5f[key].attrs.get(f'{key}_lab_radiance_add_offset', 0.0)
                    
                    # Pass h5f as argument to process_single_band
                    if result := self.process_single_band(key, data, h5f, scale_factor, add_offset):
                        results[key] = result
                        print(f"Successfully processed and uploaded {key}")
            
            print("\n=== Processing Summary ===")
            print(f"Total bands processed: {len(results)}")
            print(f"Processed bands: {', '.join(results.keys())}")
            return results
            
        except Exception as e:
            print(f"\nError processing file: {str(e)}")
            raise
        finally:
            duration = time.time() - self.start_time
            print(f"\n=== Processing Complete ===")
            print(f"Total duration: {duration:.2f} seconds")

    def _get_crs(self) -> CRS:
        """Get the coordinate reference system"""
        try:
            return CRS.from_dict({
                'proj': 'merc',
                'lon_0': 77.25,
                'lat_ts': 17.75,
                'x_0': 0,
                'y_0': 0,
                'a': 6378137,
                'b': 6356752.3142,
                'units': 'm',
                'no_defs': True
            })
        except Exception as e:
            print(f"Error creating CRS: {str(e)}")
            # Fallback to EPSG:3857 (Web Mercator)
            return CRS.from_epsg(3857)

    def _get_transform(self, shape: Tuple[int, int]):
        """Get the geotransform for the given shape"""
        print(f"Calculating transform for shape: {shape}")
        
        try:
            # Create transformer for coordinate conversion
            transformer = Transformer.from_crs(
                CRS.from_epsg(4326),  # WGS84
                self._get_crs(),
                always_xy=True
            )
            print("Created coordinate transformer")

            # Transform bounds
            print("Transforming bounds...")
            left, bottom = transformer.transform(self.bounds['left'], self.bounds['bottom'])
            right, top = transformer.transform(self.bounds['right'], self.bounds['top'])
            print(f"Transformed bounds: ({left}, {bottom}) -> ({right}, {top})")

            # Create transform
            transform = from_bounds(left, bottom, right, top, shape[1], shape[0])
            print("Transform created successfully")
            
            return transform
            
        except Exception as e:
            print(f"Error creating transform: {str(e)}")
            raise

def extract_and_project_subdatasets(h5_file_path: str, output_dir: str):
    processor = L1CProcessor(
        input_path=h5_file_path,
        output_bucket=os.environ.get('DESTINATION_BUCKET', 'final-cog')
    )
    return processor.process()

def lambda_handler(event, context):
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        # Get bucket names from environment variables with validation
        source_bucket = os.environ.get('SOURCE_BUCKET')
        destination_bucket = os.environ.get('DESTINATION_BUCKET')
        
        if not source_bucket or not destination_bucket:
            raise ValueError("SOURCE_BUCKET and DESTINATION_BUCKET environment variables must be set")
            
        # Construct proper S3 path
        input_path = f"{bucket}/{key}"
        
        print(f"Processing L1C file:")
        print(f"Source bucket: {bucket}")
        print(f"Source key: {key}") 
        print(f"Destination bucket: {destination_bucket}")
        
        processor = L1CProcessor(
            input_path=input_path,
            output_bucket=destination_bucket
        )
        
        results = processor.process()
        
        if not results:
            raise Exception("No output files generated")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing completed successfully',
                'processed_bands': list(results.keys()),
                'file_type': 'L1C' if 'L1C' in key else 'L1B',
                'processed_file': key
            })
        }
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }