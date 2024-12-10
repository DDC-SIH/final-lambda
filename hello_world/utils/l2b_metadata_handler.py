from .base_metadata_handler import MetadataHandler
import logging
import json
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class L2BMetadataHandler(MetadataHandler):
    """Handle metadata extraction and processing for L2B data"""
    
    def __init__(self, region: str = 'ap-south-1'):
        self.region = region

    def extract_metadata(self, h5_file_path: str) -> Dict[str, Any]:
        """Extract L2B specific metadata from HDF5 file"""
        try:
            with open(h5_file_path, 'r') as f:
                raw_metadata = json.load(f)
            
            timestamp = datetime.now().isoformat()
            return self._process_metadata(raw_metadata, timestamp)
            
        except Exception as e:
            logger.error(f"Error extracting L2B metadata: {str(e)}")
            raise

    def _process_metadata(self, raw_metadata: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Process L2B specific metadata"""
        try:
            # Base metadata fields
            processed = {
                'processing_timestamp': timestamp,
                'acquisition_timestamp': raw_metadata.get('Acquisition_Time_in_GMT', ''),
                'processing_level': 'L2B',
                'satellite_name': raw_metadata.get('Satellite_Name', ''),
                'sensor_id': raw_metadata.get('Sensor_Id', ''),
                'unique_id': raw_metadata.get('Unique_Id', '')
            }
            
            # Add L2B specific fields
            l2b_fields = {
                'product_type': raw_metadata.get('Product_Type', 'ATMOSPHERIC_PROFILE'),
                'algorithm_version': raw_metadata.get('Algorithm_Version', ''),
                'profile_info': {
                    'parameters': raw_metadata.get('Profile_Parameters', ''),
                    'quality_flags': raw_metadata.get('Quality_Flags', ''),
                    'vertical_levels': raw_metadata.get('Vertical_Levels', '')
                },
                'atmospheric_params': {
                    'temperature': raw_metadata.get('Temperature_Profile', ''),
                    'humidity': raw_metadata.get('Humidity_Profile', ''),
                    'pressure': raw_metadata.get('Pressure_Profile', '')
                }
            }
            processed.update(l2b_fields)
            
            return processed

        except Exception as e:
            logger.error(f"Error processing L2B metadata: {str(e)}")
            raise