from .base_metadata_handler import MetadataHandler
import logging
import json
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class L1CMetadataHandler(MetadataHandler):
    """Handle metadata extraction and processing for L1C data"""
    
    def __init__(self, region: str = 'ap-south-1'):
        self.region = region

    def extract_metadata(self, h5_file_path: str) -> Dict[str, Any]:
        """Extract L1C specific metadata from HDF5 file"""
        try:
            with open(h5_file_path, 'r') as f:
                raw_metadata = json.load(f)
            
            timestamp = datetime.now().isoformat()
            return self._process_metadata(raw_metadata, timestamp)
            
        except Exception as e:
            logger.error(f"Error extracting L1C metadata: {str(e)}")
            raise

    def _process_metadata(self, raw_metadata: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Process L1C specific metadata"""
        try:
            # Base metadata fields
            processed = {
                'processing_timestamp': timestamp,
                'acquisition_timestamp': raw_metadata.get('Acquisition_Time_in_GMT', ''),
                'processing_level': 'L1C',
                'satellite_name': raw_metadata.get('Satellite_Name', ''),
                'sensor_id': raw_metadata.get('Sensor_Id', ''),
                'unique_id': raw_metadata.get('Unique_Id', '')
            }
            
            # Add L1C specific fields
            l1c_fields = {
                'product_type': raw_metadata.get('Product_Type', 'SECTOR'),
                'projection_info': {
                    'grid_mapping': raw_metadata.get('Projection_Information_grid_mapping_name', ''),
                    'longitude_origin': raw_metadata.get('Projection_Information_longitude_of_projection_origin', ''),
                    'semi_major_axis': raw_metadata.get('Projection_Information_semi_major_axis', ''),
                    'semi_minor_axis': raw_metadata.get('Projection_Information_semi_minor_axis', '')
                },
                'geographic_boundaries': {
                    'upper_left': raw_metadata.get('Projection_Information_upper_left_lat_lon(degrees)', ''),
                    'upper_right': raw_metadata.get('Projection_Information_upper_right_lat_lon(degrees)', ''),
                    'lower_left': raw_metadata.get('Projection_Information_lower_left_lat_lon(degrees)', ''),
                    'lower_right': raw_metadata.get('Projection_Information_lower_right_lat_lon(degrees)', '')
                }
            }
            processed.update(l1c_fields)
            
            return processed

        except Exception as e:
            logger.error(f"Error processing L1C metadata: {str(e)}")
            raise