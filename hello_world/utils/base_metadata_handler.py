import logging
import json
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class MetadataHandler:
    """Base class for handling metadata extraction and processing"""
    
    def __init__(self, region: str = 'ap-south-1'):
        self.region = region

    def extract_metadata(self, h5_file_path: str) -> Dict[str, Any]:
        """Extract metadata from HDF5 file - to be implemented by subclasses"""
        raise NotImplementedError

    def _process_metadata(self, raw_metadata: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """Process metadata - to be implemented by subclasses"""
        raise NotImplementedError
