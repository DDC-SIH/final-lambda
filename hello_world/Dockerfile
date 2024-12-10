FROM public.ecr.aws/lambda/python:3.9

# Install necessary dependencies
RUN yum -y install curl unzip wget bash && \
    yum clean all


# Install Miniconda
RUN mkdir -p ${LAMBDA_TASK_ROOT}/miniconda3 && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ${LAMBDA_TASK_ROOT}/miniconda3/miniconda.sh && \
    bash ${LAMBDA_TASK_ROOT}/miniconda3/miniconda.sh -b -u -p ${LAMBDA_TASK_ROOT}/miniconda3 && \
    rm ${LAMBDA_TASK_ROOT}/miniconda3/miniconda.sh

ENV PATH=${LAMBDA_TASK_ROOT}/miniconda3/bin:$PATH

# Update and install necessary conda packages
RUN conda update sqlite && \
    conda install -c conda-forge python=3.9 gdal=3.2 libgdal=3.2 proj hdf5 h5py rasterio s3fs botocore==1.21.0 pyproj numpy && \
    conda clean -a -y

# Install pip packages in conda environment
RUN ${LAMBDA_TASK_ROOT}/miniconda3/bin/conda run -n base pip install awslambdaric boto3 psutil

# Verify installations
RUN conda --version && \
    conda list gdal && \
    find ${LAMBDA_TASK_ROOT}/miniconda3/ -name gdal_translate && \
    gdal_translate --version

# Configure Python and paths
RUN mv /var/lang/bin/python3.9 /var/lang/bin/python3.9-clean && \
    ln -sf ${LAMBDA_TASK_ROOT}/miniconda3/bin/python /var/lang/bin/python3.9 && \
    ln -sf ${LAMBDA_TASK_ROOT}/miniconda3/bin/conda /var/lang/bin/conda

# Set environment variables
ENV PYTHONPATH="/var/lang/lib/python3.9/site-packages:/opt/my-code"
ENV GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
ENV CPL_VSIL_USE_TEMP_FILE_FOR_RANDOM_WRITE=YES
ENV GDAL_HTTP_TIMEOUT=3600
ENV VSI_CACHE=TRUE
ENV VSI_CACHE_SIZE=5242880
ENV AWS_REQUEST_PAYER=requester
ENV CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif,.tiff,.h5
ENV GDAL_CACHEMAX=256
ENV VSI_MALLOC_TRIM_THRESHOLD_BYTES=5000000
ENV GDAL_MAX_DATASET_POOL_SIZE=256
ENV PROJ_LIB=${LAMBDA_TASK_ROOT}/miniconda3/share/proj

# Copy application code
COPY . ${LAMBDA_TASK_ROOT}

# Create symbolic links for GDAL tools
# RUN ln -sf ${LAMBDA_TASK_ROOT}/miniconda3/bin/gdalinfo /var/task/miniconda3/bin/gdalinfo && \
#     ln -sf ${LAMBDA_TASK_ROOT}/miniconda3/bin/gdal_translate /var/task/miniconda3/bin/gdal_translate && \
#     ln -sf ${LAMBDA_TASK_ROOT}/miniconda3/bin/gdalwarp /var/task/miniconda3/bin/gdalwarp

# Install boto3
# RUN pip install boto3

# Set the entry point to run the Python app using conda
# CMD ["conda", "run", "--no-capture-output", "-n", "base", "python", "-m", "awslambdaric"]
CMD ["app.lambda_handler"]