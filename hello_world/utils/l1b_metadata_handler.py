from .base_metadata_handler import MetadataHandler
import logging
import json
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class L1BMetadataHandler(MetadataHandler):
    """Handle metadata extraction and processing for L1B data"""
    
    def __init__(self, region: str = 'ap-south-1'):
        self.region = region
    
    def extract_metadata(self, h5_file_path: str) -> Dict[str, Any]:
        """Extract L1B specific metadata from HDF5 file"""
        try:
            with open(h5_file_path, 'r') as f:
                raw_metadata = json.load(f)
            
            timestamp = datetime.now().isoformat()
            return self._process_metadata(raw_metadata, timestamp)
            
        except Exception as e:
            logger.error(f"Error extracting L1B metadata: {str(e)}")
            raise

    def _process_metadata(self, raw_metadata: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Process L1B specific metadata"""
        try:
            # Base metadata fields
            processed = {
                'processing_timestamp': timestamp,
                'acquisition_timestamp': raw_metadata.get('Acquisition_Time_in_GMT', ''),
                'processing_level': 'L1B',
                'satellite_name': raw_metadata.get('Satellite_Name', ''),
                'sensor_id': raw_metadata.get('Sensor_Id', ''),
                'unique_id': raw_metadata.get('Unique_Id', '')
            }
            
            # Add L1B specific fields
            l1b_fields = {
                'product_type': raw_metadata.get('Product_Type', 'STANDARD (FULL DISK)'),
                'radiometric_calibration': raw_metadata.get('Radiometric_Calibration_Type', ''),
                'acquisition_modes': {
                    'mir': raw_metadata.get('MIR_Acquisition_Mode', ''),
                    'tir1': raw_metadata.get('TIR1_Acquisition_Mode', ''),
                    'tir2': raw_metadata.get('TIR2_Acquisition_Mode', ''),
                    'vis': raw_metadata.get('VIS_Acquisition_Mode', ''),
                    'wv': raw_metadata.get('WV_Acquisition_Mode', '')
                },
                'gain_modes': {
                    'mir': raw_metadata.get('MIR_Gain_Mode', ''),
                    'tir1': raw_metadata.get('TIR1_Gain_Mode', ''),
                    'tir2': raw_metadata.get('TIR2_Gain_Mode', ''),
                    'vis': raw_metadata.get('VIS_Gain_Mode', ''),
                    'wv': raw_metadata.get('WV_Gain_Mode', '')
                }
            }
            processed.update(l1b_fields)
            
            return processed

        except Exception as e:
            logger.error(f"Error processing L1B metadata: {str(e)}")
            raise