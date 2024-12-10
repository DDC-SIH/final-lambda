import json
import os
import boto3
import logging
import subprocess
import concurrent.futures
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from botocore.config import Config

# Import dataset extraction scripts
from dataset_extraction_scripts.l1bconvertandupload import process_file
from dataset_extraction_scripts.l1bconvertandupload import INSAT3DProcessor
from dataset_extraction_scripts.l1cconvertandupload import (
    L1CProcessor,
    extract_and_project_subdatasets
)
from utils.l1c_metadata_handler import L1CMetadataHandler

# Configure logging with more detail
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def lambda_handler(event, context):
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        local_file_path = f"/tmp/processing/{key}"
        output_dir = "/tmp/output"
        
        logger.info(f"Starting processing for file: {key} in bucket: {bucket}")
        print(f"Starting processing for file: {key} in bucket: {bucket}")
        
        result = process_satellite_data(key, local_file_path, output_dir)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        logger.error(f"Lambda processing failed: {str(e)}")
        print(f"Lambda processing failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def determine_data_type(filename: str) -> str:
    """Determine the data type from filename"""
    logger.info(f"Determining data type for file: {filename}")
    print(f"Determining data type for file: {filename}")
    if '_L1B_' in filename:
        return 'L1B'
    elif '_L1C_' in filename:
        return 'L1C'
    elif '_L2B_' in filename:
        return 'L2B'
    elif '_L2C_' in filename:
        return 'L2C'
    else:
        raise ValueError(f"Unknown data type in filename: {filename}")

def get_metadata_handler(data_type: str):
    """Get appropriate metadata handler based on data type"""
    logger.info(f"Getting metadata handler for data type: {data_type}")
    print(f"Getting metadata handler for data type: {data_type}")
    region = os.environ.get('AWS_DEFAULT_REGION', 'ap-south-1')
    handlers = {
        'L1B': None,  # Replace with actual L1BMetadataHandler if available
        'L1C': L1CMetadataHandler(region=region),
        'L2B': None,  # Replace with actual L2BMetadataHandler if available
        'L2C': None   # Replace with actual L2CMetadataHandler if available
    }
    print(f"Handlers dictionary: {handlers}")
    handler = handlers.get(data_type)
    print(f"Selected handler: {handler}")
    return handler

def process_bands(data_type: str, h5_file_path: str, output_dir: str):
    """Process bands based on data type"""
    logger.info(f"Processing bands for data type: {data_type}")
    print(f"Processing bands for data type: {data_type}")
    if data_type in ['L1B', 'L1C']:
        return extract_and_project_subdatasets(h5_file_path, output_dir)
    elif data_type == 'L2B':
        # TODO: Implement L2B specific processing
        # Expected to handle atmospheric parameters, vertical profiles
        return process_l2b_data(h5_file_path, output_dir)
    elif data_type == 'L2C':
        # TODO: Implement L2C specific processing
        # Expected to handle derived products, gridded data
        return process_l2c_data(h5_file_path, output_dir)
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

def process_l2b_data(h5_file_path: str, output_dir: str):
    """Process Level-2B data"""
    logger.info(f"Processing Level-2B data from file: {h5_file_path}")
    print(f"Processing Level-2B data from file: {h5_file_path}")
    # TODO: Implement L2B processing logic
    # Example:
    # - Extract atmospheric profiles
    # - Process temperature/humidity layers
    # - Generate derived products
    pass

def process_l2c_data(h5_file_path: str, output_dir: str):
    """Process Level-2C data"""
    logger.info(f"Processing Level-2C data from file: {h5_file_path}")
    print(f"Processing Level-2C data from file: {h5_file_path}")
    # TODO: Implement L2C processing logic
    # Example:
    # - Process gridded data
    # - Extract geophysical parameters
    # - Generate final products
    pass

def extract_and_project_subdatasets(h5_file_path: str, output_dir: str):
    """
    Extract and project base image subdatasets from HDF5 file using Mercator projection
    """
    logger.info(f"Extracting and projecting subdatasets from file: {h5_file_path}")
    print(f"Extracting and projecting subdatasets from file: {h5_file_path}")
    processor = L1CProcessor(
        input_path=h5_file_path,
        output_bucket=os.environ.get('DESTINATION_BUCKET', 'final-cog')
    )
    return processor.process()

def create_s3_client():
    """Create S3 client with proper configuration"""
    config = Config(
        region_name=os.environ.get('AWS_DEFAULT_REGION', 'ap-south-1'),
        retries={
            'max_attempts': 3,
            'mode': 'standard'
        }
    )
    return boto3.client(
        's3',
        config=config,
        aws_access_key_id='AKIAWEJRDA3QOVOK5EWE',
        aws_secret_access_key='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'
    )

def process_satellite_data(filename: str, input_path: str, output_dir: str):
    """Main processing pipeline for satellite data"""
    try:
        print("\n============================================")
        print("=== Starting Satellite Data Processing Pipeline ===")
        print("============================================")
        print(f"File: {filename}")
        print(f"Input path: {input_path}")
        print(f"Output directory: {output_dir}")
        logger.info("=== Starting Satellite Data Processing Pipeline ===")

        # Step 1: Create necessary directories
        print("\n=== Step 1: Creating Directories ===")
        print(f"Creating directory: {os.path.dirname(input_path)}")
        print(f"Creating directory: {output_dir}")
        os.makedirs(os.path.dirname(input_path), exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
        print("Directories created successfully")

        # Step 2: Determine data type
        print("\n=== Step 2: Determining Data Type ===")
        data_type = determine_data_type(filename)
        print(f"Detected data type: {data_type}")

        # Step 3: Copy file from S3 to local with better error handling
        print(f"\n=== Step 3: Copying File from S3 ===")
        try:
            s3_client = create_s3_client()
            source_bucket = os.environ.get('SOURCE_BUCKET', 'kdg-raw')
            dest_bucket = os.environ.get('DESTINATION_BUCKET', 'final-cog')
            
            print(f"Source bucket: {source_bucket}")
            print(f"Source file: {filename}")
            print(f"Destination: {input_path}")
            
            # Check if file exists first
            try:
                s3_client.head_object(Bucket=source_bucket, Key=filename)
            except Exception as e:
                if '403' in str(e):
                    raise Exception(f"Permission denied accessing {source_bucket}/{filename}. Please check IAM roles.")
                elif '404' in str(e):
                    raise Exception(f"File {filename} not found in bucket {source_bucket}")
                else:
                    raise
            
            # Download file if exists
            s3_client.download_file(source_bucket, filename, input_path)
            print("File downloaded successfully")
            
        except Exception as e:
            detailed_error = f"Failed to download file: {str(e)}\n"
            detailed_error += f"Bucket: {source_bucket}\n"
            detailed_error += f"Key: {filename}\n"
            detailed_error += f"AWS Region: {os.environ.get('AWS_DEFAULT_REGION', 'ap-south-1')}\n"
            detailed_error += f"IAM Role: {os.environ.get('AWS_ROLE_ARN', 'Not specified')}"
            logger.error(detailed_error)
            raise Exception(detailed_error)

        # Step 4: Generate products
        print(f"\n=== Step 4: Generating Products ===")
        print(f"Processing {data_type} data...")
        
        if data_type == 'L1C':
            processor = L1CProcessor(
                input_path=f"s3://{source_bucket}/{filename}",  # Use proper S3 path
                output_bucket=dest_bucket
            )
            generation_result = processor.process()
        else:
            generation_result = generate_products(data_type, input_path, output_dir)
            
        print("Product generation complete")
        print(f"Generation result: {generation_result}")

        # Step 5: Handle metadata
        print(f"\n=== Step 5: Processing Metadata ===")
        metadata_handler = get_metadata_handler(data_type)
        print(f"Metadata handler obtained: {metadata_handler}")
        if metadata_handler:
            print(f"Using {data_type} metadata handler: {metadata_handler}")
            print("Extracting metadata...")
            print(f"Input path for metadata extraction: {input_path}")
            metadata_result = metadata_handler.extract_metadata(input_path)
            print(f"Metadata extraction result: {metadata_result}")
            print("Metadata extraction complete")
        else:
            print(f"No metadata handler available for data type: {data_type}")
            metadata_result = {}

        # Step 6: Cleanup
        print("\n=== Step 6: Cleanup ===")
        try:
            os.remove(input_path)
            print(f"Removed temporary file: {input_path}")
        except Exception as e:
            print(f"Cleanup warning: {str(e)}")

        print("\n============================================")
        print("=== Processing Pipeline Complete ===")
        print("============================================")
        
        return {
            'statusCode': 200,
            'body': {
                'data_type': data_type,
                'generated_files': generation_result,
                'metadata': metadata_result
            }
        }
    except Exception as e:
        print(f"\n!!! Processing Failed !!!")
        print(f"Error: {str(e)}")
        logger.error(f"Processing failed: {str(e)}")
        raise

def generate_products(data_type: str, input_path: str, output_dir: str) -> dict:
    """Route to appropriate generation function based on data type"""
    logger.info(f"=== Starting Product Generation for {data_type} ===")
    print(f"=== Starting Product Generation for {data_type} ===")
    
    generators = {
        'L1B': generate_l1b_products,
        'L1C': generate_l1c_products,
        'L2B': generate_l2b_products,
        'L2C': generate_l2c_products
    }
    
    generator = generators.get(data_type)
    if not generator:
        msg = f"No generator found for {data_type}"
        logger.error(msg)
        print(msg)
        raise ValueError(msg)
    
    logger.info(f"Executing {data_type} product generation")
    print(f"Executing {data_type} product generation")
    result = generator(input_path, output_dir)
    
    logger.info(f"=== Product Generation Complete for {data_type} ===")
    print(f"=== Product Generation Complete for {data_type} ===")
    return result

def generate_l1b_products(input_path: str, output_dir: str) -> dict:
    """Generate L1B products"""
    logger.info("Generating L1B products...")
    print("Generating L1B products...")
    # TODO: Implement L1B specific generation
    # - Extract radiance data
    # - Apply calibration
    # - Generate quick looks
    return {'status': 'generated', 'type': 'L1B'}

def generate_l1c_products(input_path: str, output_dir: str) -> dict:
    """Generate L1C products"""
    logger.info("Generating L1C products...")
    print("Generating L1C products...")
    
    processor = L1CProcessor(
        input_path=input_path,
        output_bucket=os.environ.get('DESTINATION_BUCKET', 'final-cog')
    )
    results = processor.process()
    
    return {
        'status': 'generated',
        'type': 'L1C',
        'processed_bands': results
    }

def generate_l2b_products(input_path: str, output_dir: str) -> dict:
    """Generate L2B products"""
    logger.info("Generating L2B products...")
    print("Generating L2B products...")
    # TODO: Implement L2B specific generation
    # - Generate atmospheric profiles
    # - Calculate derived parameters
    return {'status': 'generated', 'type': 'L2B'}

def generate_l2c_products(input_path: str, output_dir: str) -> dict:
    """Generate L2C products"""
    logger.info("Generating L2C products...")
    print("Generating L2C products...")
    # TODO: Implement L2C specific generation
    # - Generate gridded products
    # - Apply advanced algorithms
    return {'status': 'generated', 'type': 'L2C'}