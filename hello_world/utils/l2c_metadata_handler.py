from .base_metadata_handler import MetadataHandler
import logging
import json
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class L2CMetadataHandler(MetadataHandler):
    """Handle metadata extraction and processing for L2C data"""
    
    def __init__(self, region: str = 'ap-south-1'):
        self.region = region

    def extract_metadata(self, h5_file_path: str) -> Dict[str, Any]:
        """Extract L2C specific metadata from HDF5 file"""
        try:
            with open(h5_file_path, 'r') as f:
                raw_metadata = json.load(f)
            
            timestamp = datetime.now().isoformat()
            return self._process_metadata(raw_metadata, timestamp)
            
        except Exception as e:
            logger.error(f"Error extracting L2C metadata: {str(e)}")
            raise

    def _process_metadata(self, raw_metadata: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Process L2C specific metadata"""
        try:
            # Base metadata fields
            processed = {
                'processing_timestamp': timestamp,
                'acquisition_timestamp': raw_metadata.get('Acquisition_Time_in_GMT', ''),
                'processing_level': 'L2C',
                'satellite_name': raw_metadata.get('Satellite_Name', ''),
                'sensor_id': raw_metadata.get('Sensor_Id', ''),
                'unique_id': raw_metadata.get('Unique_Id', '')
            }
            
            # Add L2C specific fields
            l2c_fields = {
                'product_type': raw_metadata.get('Product_Type', 'GRIDDED_PRODUCT'),
                'grid_info': raw_metadata.get('Grid_Information', ''),
                'map_projection': raw_metadata.get('Map_Projection', ''),
                'derived_parameters': raw_metadata.get('Derived_Parameters', ''),
                'processing_params': raw_metadata.get('Processing_Parameters', ''),
                'quality_info': {
                    'flags': raw_metadata.get('Quality_Flags', ''),
                    'indicators': raw_metadata.get('Quality_Indicators', ''),
                    'statistics': raw_metadata.get('Quality_Statistics', '')
                }
            }
            processed.update(l2c_fields)
            
            return processed

        except Exception as e:
            logger.error(f"Error processing L2C metadata: {str(e)}")
            raise