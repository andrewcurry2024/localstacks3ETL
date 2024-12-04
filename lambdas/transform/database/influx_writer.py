from influxdb_client import InfluxDBClient, WriteOptions, Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
from utils.s3 import get_secret

class Database:
    def __init__(self):
        try:
            secret_name = "influxdb-secrets"
            secrets = get_secret(secret_name)
            print("HELLO")
            print(secrets)

            # Validate that required secrets are present
            if not secrets or not all(k in secrets for k in ('token', 'org', 'bucket')):
                raise ValueError("Missing required secrets keys: 'token', 'org', or 'bucket'")
            self.token = secrets['token']
            self.org = secrets['org']
            self.bucket = secrets['bucket']
            self.url = "http://influxdb:8086"

        except Exception as e:
            # Log and raise the exception for visibility
            print(f"Error initializing Database class: {e}")
            raise


    def write_summary_record(self, write_api, customer, server, filename):
        try:
            # Ensure that the data values are valid
            if not customer or not server or not filename:
                raise ValueError(f"Invalid data for summary: customer={customer}, server={server}, filename={filename}")
        
            # Get the current time in UTC and format it (same as your previous code)
            current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
            # Create the summary point
            summary_point = (
                Point("customer_server")  # Measurement name
                .field("customer", customer)
                .field("server", server)
                .field("filename", filename)
                .field("_time", current_time)
                .field("datetime", current_time)
            )
        
            print(f"Writing summary_point for customer={customer}, server={server}, filename={filename} at {current_time}")
        
            # Write the summary point to InfluxDB
            write_api.write(bucket=self.bucket, org=self.org, record=summary_point)
    
        except Exception as e:
            # Print the error with details for debugging
            print(f"An unexpected error occurred while writing data for {filename} to customer_server: {customer}")
            print(f"Error details: {str(e)}")

    def write(self, data, file,customer,server):
        """Write data to InfluxDB using batching with context management"""
        try:
            # Open the client and write_api in a 'with' statement to ensure proper management
            with InfluxDBClient(url=self.url, token=self.token) as client:
                # Set write options: batch size, flush interval, jitter, etc.
                write_options = WriteOptions(batch_size=1000, flush_interval=100, jitter_interval=100)
                # Use write_api within the context
                with client.write_api(write_options=write_options) as write_api:
                    self.write_summary_record(write_api, customer, server, file)
                    # Loop through each record and write it to InfluxDB
                    for record in data:
                        # Prepare the record for writing
                        if 'datetime' in record:
                            record['_time'] = record.pop('datetime')
                            if isinstance(record['_time'], str):
                                record['_time'] = datetime.strptime(record['_time'], '%Y-%m-%dT%H:%M:%S')
                            record['_time'] = record['_time'].replace(tzinfo=None)
                            record['_time'] = record['_time'].strftime('%Y-%m-%dT%H:%M:%SZ')

                        point = Point(record['_measurement'])

                        # Add tags and fields dynamically
                        if "customer" in record:
                            point.tag("customer", record["customer"])
                        if "server" in record:
                            point.tag("server", record["server"])
                        if "digits" in record:
                            point.tag("pagesize", record["digits"])
                        if "name" in record:
                            point.tag("metric", record["name"])
                        if "area" in record:
                            point.tag("metric", record["area"])

                        for field, value in record.items():
                            if field not in ['_measurement', 'customer', 'server', '_time']:
                                point.field(field, value)

                        point.time(record['_time'], WritePrecision.S)

                        # Write the point to InfluxDB asynchronously (handled by batching)
                        #print(f"Writing record for {file}")
                        write_api.write(bucket=self.bucket, org=self.org, record=point)

                    # Flush data to ensure all points are written before closing
                    write_api.flush()
                      # Write the summary record at the end


            print(f"All data for {file} successfully written to InfluxDB")
        except Exception as e:
            print(f"An unexpected error occurred while writing data for {file}: {e}")
