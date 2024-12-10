from .base_metadata_handler import MetadataHandler
import boto3
import h5py
import logging
import json
import os
import numpy as np
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union
import rasterio

logger = logging.getLogger(__name__)

class L1CMetadataHandler(MetadataHandler):
    def __init__(self, region: str = 'ap-south-1', table_name: str = 'L1C'):
        self.region = region
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.s3 = boto3.client('s3')

    def decode_if_bytes(self, value):
        """Decode byte strings and handle numpy arrays"""
        if isinstance(value, bytes):
            return value.decode('utf-8')
        if isinstance(value, np.generic):
            return value.item()
        return value

    def safe_float(self, value):
        """Safely convert numpy arrays or bytes to float"""
        if isinstance(value, (bytes, str)):
            value = self.decode_if_bytes(value)
        if isinstance(value, np.generic):
            return float(value.item())
        return float(value)

    def get_s3_url(self, h5_filename, band_name):
        """Generate S3 URL for a given band"""
        folder_name = h5_filename.rsplit('.', 1)[0]
        return f"https://final-cog.s3.ap-south-1.amazonaws.com/{folder_name}/{band_name}_cog.tif"

    def extract_h5_metadata(self, h5_file_path):
        """Extract metadata from H5 file and create initial metadata structure"""
        # Open the local H5 file directly
        with h5py.File(h5_file_path, 'r') as h5f:
            file_name = os.path.basename(h5_file_path)
            acquisition_date = self.decode_if_bytes(h5f.attrs['Acquisition_Date'])
            start_time = self.decode_if_bytes(h5f.attrs['Acquisition_Start_Time'])
            end_time = self.decode_if_bytes(h5f.attrs['Acquisition_End_Time'])
            time_gmt = self.decode_if_bytes(h5f.attrs['Acquisition_Time_in_GMT'])
            timestamp = datetime.strptime(f"{acquisition_date} {time_gmt}", "%d%b%Y %H%M").strftime("%Y-%m-%dT%H:%M:00Z")

            metadata = {
                "acquisition": {
                    "date": acquisition_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timestamp": timestamp,
                    "time_gmt": time_gmt
                },
                "auxiliary_data": {
                    "satellite": {
                        "azimuth": self.safe_float(h5f.attrs['Sat_Azimuth(Degrees)']),
                        "elevation": self.safe_float(h5f.attrs['Sat_Elevation(Degrees)'])
                    },
                    "sun": {
                        "azimuth": self.safe_float(h5f.attrs['Sun_Azimuth(Degrees)']),
                        "elevation": self.safe_float(h5f.attrs['Sun_Elevation(Degrees)'])
                    }
                },
                "bands": {},
                "coverage": {
                    "latitude": {
                        "lower": self.safe_float(h5f.attrs['lower_latitude']),
                        "upper": self.safe_float(h5f.attrs['upper_latitude'])
                    },
                    "longitude": {
                        "left": self.safe_float(h5f.attrs['left_longitude']),
                        "right": self.safe_float(h5f.attrs['right_longitude'])
                    }
                },
                "id": self.decode_if_bytes(h5f.attrs['Unique_Id']),
                "product_info": {
                    "creation_time": self.decode_if_bytes(h5f.attrs['Product_Creation_Time']),
                    "file_name": file_name,
                    "level": self.decode_if_bytes(h5f.attrs['Processing_Level']),
                    "title": self.decode_if_bytes(h5f.attrs['title']),
                    "type": self.decode_if_bytes(h5f.attrs['Product_Type'])
                },
                "satellite_info": {
                    "altitude": self.safe_float(h5f.attrs['Observed_Altitude(km)']),
                    "name": self.decode_if_bytes(h5f.attrs['Satellite_Name']),
                    "sensor": {
                        "id": self.decode_if_bytes(h5f.attrs['Sensor_Id']),
                        "name": self.decode_if_bytes(h5f.attrs['Sensor_Name'])
                    }
                },
                "source": {
                    "ground_station": self.decode_if_bytes(h5f.attrs['Station_Id']),
                    "institute": self.decode_if_bytes(h5f.attrs['institute'])
                }
            }

            bands = ['MIR', 'SWIR', 'TIR1', 'TIR2', 'VIS', 'WV']
            for band in bands:
                dataset_name = f'IMG_{band}'
                if dataset_name in h5f:
                    dataset = h5f[dataset_name]
                    metadata["bands"][band] = {
                        "metadata": {
                            "bandwidth": self.safe_float(dataset.attrs.get('bandwidth', 0.2)),
                            "bits_per_pixel": int(self.decode_if_bytes(dataset.attrs.get('bits_per_pixel', 10))),
                            "dimensions": {
                                "height": dataset.shape[1],
                                "width": dataset.shape[2]
                            },
                            "fill_value": int(self.decode_if_bytes(dataset.attrs.get('_FillValue', 1023))),
                            "resolution": self.safe_float(dataset.attrs.get('resolution', 4)),
                            "wavelength": self.safe_float(dataset.attrs.get('central_wavelength', 0))
                        },
                        "url": self.get_s3_url(file_name, dataset_name)
                    }

            return metadata

    def extract_metadata(self, h5_file_path):
        """Extract metadata and upload to DynamoDB"""
        filename = os.path.basename(h5_file_path)
        date_str, time_str = self._extract_date_time(filename)

        # Extract metadata from H5 file
        raw_metadata = self.extract_h5_metadata(h5_file_path)

        # Get band statistics from subdatasets stored in 'final-cog' bucket
        band_stats = self._get_band_statistics(filename)

        # Update metadata with band statistics
        for band, stats in band_stats.items():
            if band in raw_metadata['bands'] and stats:
                raw_metadata['bands'][band]['metadata']['data_range'] = stats

        # Create final metadata structure
        final_metadata = {
            "date": date_str,
            "time": [
                {
                    time_str: raw_metadata
                }
            ]
        }

        # Upload metadata to DynamoDB
        self._upload_to_dynamodb(final_metadata)
        return final_metadata

    def _get_band_statistics(self, h5_filename):
        """Get band statistics from COG files in 'final-cog' bucket"""
        bucket = os.environ.get('DESTINATION_BUCKET', 'final-cog')
        folder_name = h5_filename.rsplit('.', 1)[0]

        bands = ['IMG_MIR', 'IMG_SWIR', 'IMG_TIR1', 'IMG_TIR2', 'IMG_VIS', 'IMG_WV']
        band_stats = {}
        for band in bands:
            key = f"/vsis3/{bucket}/{folder_name}/{band}_cog.tif"
            try:
                with rasterio.open(key) as src:
                    data = src.read(1, masked=True)
                    band_stats[band.replace('IMG_', '')] = {
                        'min': float(data.min()),
                        'max': float(data.max())
                    }
            except Exception as e:
                logger.warning(f"Could not read band statistics for {band}: {e}")
                band_stats[band.replace('IMG_', '')] = None
        return band_stats

    def _extract_date_time(self, filename: str) -> Tuple[str, str]:
        """Extract date and time from filename"""
        parts = filename.split('_')
        return parts[1], parts[2]

    def _get_existing_metadata(self, date: str) -> Dict[str, Any]:
        """Retrieve existing metadata for a given date from DynamoDB"""
        try:
            response = self.table.get_item(Key={'date': date})
            return response.get('Item', {'date': date, 'time': []})
        except Exception as e:
            logger.error(f"Failed to get existing metadata: {str(e)}")
            return {'date': date, 'time': []}

    def _merge_and_sort_times(self, existing_metadata: Dict[str, Any], new_time_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Merge new time entry with existing ones, updating existing entries and removing duplicates."""
        new_time_key = list(new_time_entry.keys())[0]
        
        # Remove any entries with the same time key to avoid duplicates
        time_entries = [
            entry for entry in existing_metadata.get('time', [])
            if list(entry.keys())[0] != new_time_key
        ]
        
        # Add the new time entry
        time_entries.append(new_time_entry)
        logger.info(f"Added/Updated time entry for {new_time_key}")
        
        # Sort entries by timestamp
        def get_timestamp(entry):
            time_key = list(entry.keys())[0]
            return entry[time_key]['acquisition']['timestamp']
        
        sorted_entries = sorted(time_entries, key=get_timestamp)
        logger.info(f"Total time entries after merge: {len(sorted_entries)}")
        return sorted_entries

    def _upload_to_dynamodb(self, metadata: Dict[str, Any]) -> None:
        """Upload metadata to DynamoDB with merged time entries"""
        try:
            # Get existing metadata for the date
            date = metadata['date']
            existing_metadata = self._get_existing_metadata(date)
            
            # Get the new time entry
            new_time_entry = metadata['time'][0]
            time_key = list(new_time_entry.keys())[0]
            
            # Merge and sort time entries
            sorted_time_entries = self._merge_and_sort_times(existing_metadata, new_time_entry)
            
            # Prepare final metadata
            final_metadata = {
                'date': date,
                'time': sorted_time_entries
            }
            
            # Convert floats to Decimal
            def convert_floats(obj):
                if isinstance(obj, float):
                    return Decimal(str(obj))
                elif isinstance(obj, dict):
                    return {k: convert_floats(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_floats(i) for i in obj]
                return obj
            
            dynamo_item = convert_floats(final_metadata)
            
            # Upload to DynamoDB
            self.table.put_item(Item=dynamo_item)
            logger.info(f"Successfully uploaded metadata for date {date} and time {time_key}")
            logger.info(f"Number of time entries: {len(sorted_time_entries)}")
            
        except Exception as e:
            logger.error(f"Failed to upload to DynamoDB: {str(e)}")
            raise