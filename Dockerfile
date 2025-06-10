# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce layer size
RUN pip install --no-cache-dir -r requirements.txt

# Optional: Run crawl4ai-doctor to verify the installation during build
# This can be useful for debugging but might be removed for a leaner final image.
# RUN crawl4ai-doctor

# Copy the rest of the application code into the working directory
COPY . .
# This copies app.py, models.json, and any other files/folders in the build context.

# Make port 8501 available to the world outside this container (Streamlit default port)
EXPOSE 8501

# Define environment variable for Streamlit
# (Not strictly necessary if not changing defaults, but good practice)
ENV STREAMLIT_SERVER_PORT 8501
ENV STREAMLIT_SERVER_HEADLESS true

# Run app.py when the container launches
CMD ["streamlit", "run", "app.py"]
