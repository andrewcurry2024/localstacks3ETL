import csv
import time
import os
import re
import pandas as pd
import shutil
from datetime import datetime
from typing import List, Dict, Callable
import signal
import sys
from influxdb_client import InfluxDBClient, WriteOptions, Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS
class Database:
    def __init__(self):
        self.token = "my-super-secret-auth-token"
        self.org = "myorg"
        self.bucket = "mydb"
        self.url = "http://localhost:8086"

    def write(self, data, subroutine_key):
        """Write data to InfluxDB using batching with context management"""
        try:
            # Open the client and write_api in a 'with' statement to ensure proper management
            with InfluxDBClient(url=self.url, token=self.token) as client:
                # Set write options: batch size, flush interval, jitter, etc.
                write_options = WriteOptions(batch_size=1000, flush_interval=100, jitter_interval=100)

                # Use write_api within the context
                with client.write_api(write_options=write_options) as write_api:
                    # Loop through each record and write it to InfluxDB
                    for record in data:
                        # Prepare the record for writing
                        if 'datetime' in record:
                            record['_time'] = record.pop('datetime')
                            if isinstance(record['_time'], str):
                                record['_time'] = datetime.strptime(record['_time'], '%Y-%m-%dT%H:%M:%S')
                            record['_time'] = record['_time'].replace(tzinfo=None)
                            record['_time'] = record['_time'].strftime('%Y-%m-%dT%H:%M:%SZ')

                        record['_measurement'] = subroutine_key
                        point = Point(record['_measurement'])

                        # Add tags and fields dynamically
                        if "customer" in record:
                            point.tag("customer", record["customer"])
                        if "server" in record:
                            point.tag("server", record["server"])

                        for field, value in record.items():
                            if field not in ['_measurement', 'customer', 'server', '_time']:
                                point.field(field, value)

                        point.time(record['_time'], WritePrecision.S)

                        # Write the point to InfluxDB asynchronously (handled by batching)
                        print(f"Writing record for {subroutine_key}: {point}")
                        write_api.write(bucket=self.bucket, org=self.org, record=point)

                    # Flush data to ensure all points are written before closing
                    write_api.flush()

            print(f"All data for {subroutine_key} successfully written to InfluxDB")
        except Exception as e:
            print(f"An unexpected error occurred while writing data for {subroutine_key}: {e}")

# Simulated logger
class Logger:
    def error(self, message):
        print(f"ERROR: {message}")
    def debug(self, message):
        print(f"INFO: {message}")
class Config:
    INDIR = "./in"
    OUTDIR = "./out"

def clean_data(df: pd.DataFrame, header: str, customer: str, server: str) -> pd.DataFrame:
    """
    Clean the data by adding customer, server, renaming columns according to the header,
    and combining date and time into a single datetime column.
    """
    df = df.copy()  # Ensure that we're working with a fresh copy of the dataframe

    for column in df.columns:
        if column not in ['datetime', 'customer', 'server']:  # Skip special columns
            # Use .loc to modify values to avoid the SettingWithCopyWarning
            condition_large_value = (df[column].apply(lambda x: isinstance(x, (int, float)) and x > 9023372036854775800))
            condition_nan = (df[column].apply(lambda x: isinstance(x, str) and x.lower() == 'nan'))

            # Set invalid values to -1
            df.loc[condition_large_value, column] = -1
            df.loc[condition_nan, column] = -1

    # Combine date and time columns (assuming there's a 'datetime' column)
    if 'datetime' in df.columns:
        # If a 'datetime' column already exists, ensure it's in datetime format
        df['datetime'] = pd.to_datetime(df['datetime'])
    else:
        # If 'datetime' isn't there, attempt to combine 'date' and 'time' columns
        if 'date' in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
            df.drop(columns=['date', 'time'], inplace=True)
        else:
            print("ERROR: No 'datetime', 'date', or 'time' columns found!")

    # 3. Ensure datetime is the first column
    if 'datetime' in df.columns:
        cols = ['datetime'] + [col for col in df.columns if col != 'datetime']
        df = df[cols]
    else:
        print("ERROR: 'datetime' column not found!")

    # 4. Rename the columns based on the header
    header_columns = header.split(',')

    # Ensure that the DataFrame has at least as many columns as the header
    if len(header_columns) < len(df.columns):
        # Trim the DataFrame to match the number of columns in the header
        df = df.iloc[:, :len(header_columns)]

    # Rename the columns based on the header
    if len(header_columns) == len(df.columns):
        # Map each column by index (0 -> 0, 1 -> 1, etc.)
        df.columns = header_columns
    else:
        print(f"ERROR: Column count mismatch: header has {len(header_columns)} columns, but dataframe has {len(df.columns)} columns.")

    # Set 'customer' and 'server' values using .loc
    df.loc[:, 'customer'] = customer
    df.loc[:, 'server'] = server

    # Print cleaned data overview
    print(f"Cleaned Data Overview for {customer}-{server}:")
    print(df.info())

    return df


def import_data(header, filename, db,customer,server,subroutine_key):
    try:
        # Read the file into a DataFrame
        records=[]
        df = pd.read_csv(filename, header=0)  # Use the first row as headers
        df.columns = df.columns.str.strip()
        df = clean_data(df,header,customer,server)
        print(f"DataFrame for {filename} with header: {header}")
        print(df)  # Print out the DataFrame
	# try write them using db object
        records = df.to_dict(orient="records")
        db.write(records,subroutine_key)  # Send to InfluxDB

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def import_data_onstat_l(header, filename, db,customer,server,subroutine_key):
    try:
        column_names = ['date', 'time', 'epoch', 'pbuffer', 'pbufused', 'pbufsize', 'ppct_io', 'lbuffer', 'lbufused', 'lbufsize', 'physused']

# Load the CSV file with custom headers
        df = pd.read_csv(
            filename,
            names=column_names,  # Use custom column names
            header=0,  # The first row will be skipped (since you are providing column names)
            encoding='utf-8',  # Ensure the encoding is correct
            skip_blank_lines=True,  # Skip blank lines if any
            on_bad_lines='skip',  # Skip any problematic lines
            delimiter=','  # Specify comma as delimiter
        )
        df.columns = df.columns.str.strip()
        df = clean_data(df,header,customer,server)
	# try write them using db object
        records = df.to_dict(orient="records")
        db.write(records,subroutine_key)  # Send to InfluxDB
        print(f"DataFrame for {filename} with header: {header}")
        print(df)  # Print out the DataFrame

        # Here, you'd implement any additional logic needed for data processing
    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

# Modify the cpu_by_app function similarly
def cpu_by_app(header, filename, db,customer,server,subroutine_key):
    try:
        # Read the file into a DataFrame
        df = pd.read_csv(filename, header=0)
        #df = clean_data(df,header,customer,server)
        ##print(f"DataFrame for {filename} with header: {header}")
        #print(df)  # Print out the DataFrame

        # Implement additional processing logic here if needed
    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

# Define subroutine dictionary with routine mappings and headers
subroutines = {
    'bpm': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['bets_per_min', 'datetime,bpm']]}
    },
    'checkpoints': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['checkpoint_info',
'datetime,id,intvl,type,caller,clock_time,crit_time,flush_time,cp_time,n_dirty_buffs,plogs_per_sec,llogs_per_sec,dskflush_per_sec,ckpt_logid,ckpt_logpos,physused,logused,n_crit_waits,tot_crit_wait,longest_crit_wait,block_time']]}
    },
    'osmon_sum': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['osmon', 'datetime,rmbs_tot,wmbs_tot,await_avg,pctutil_avg,await_hotcnt,await_hotavg,svctm_hotcnt,svctm_hotavg,pctutil_hotcnt,pctutil_hotavg,cpu_avg_busy,eth_rxbytpers,eth_txbytpers,eth_totMBpers']]}
    },
    'queues_summary': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['queue_summary', 'datetime,act_avg,rea_avg,rea_rep_pct,mtx_avg,con_avg,lck_mtx_avg']]}
    },
    'onstat-u': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['thread_states', 'datetime,write_to_logical_log,buffer_waits,checkpoint_waits,lock_waits,mutex_waits,transaction_waits,trans_cleanup,condition_waits,total,engine_status']]}
    },
    'replication': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['replication_info', "datetime,current_log,current_page,replication_server,ack_log,ack_page,app_log,app_page,backlog,type,Status"]]}
    },
    'cpu_by_app': {
        'SUB': cpu_by_app,
        'VALUES': {'IMPORT': [['cpu_by_app', "datetime,name,cores,percentage"]]}
    },
    'openbet_cpu_by_app': {
        'SUB': cpu_by_app,
        'VALUES': {'IMPORT': [['cpu_by_app', "datetime,name,cores,percentage"]]}
    },
    'db_check_info': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['dbmonitor_alert', "datetime,text"]]}
    },
    'total_locks': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['total_locks', "datetime,total_locks"]]}
    },
    'onstat-g_ntu': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['network_stats', "datetime,connects,total_reads,total_writes"]]}
    },
    'buffer_k': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['buffers', "datetime,ps,dskreads,pagreads,bufreads,per_read_cached,dskwrits,pagwrits,bufwrits,per_writecached,bufwrits_sinceckpt,bufwaits,ovbuff,flushes,Fg_Writes,LRU_Writes,Avg_LRU_Time,Chunk_Writes"]]}
    },
    'buffer_fast': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['buffer_fast', "datetime,gets,hits,percent_hits,puts"]]}
    },
    'lru_overall': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['lru_overall', "datetime,overall,dirtyGBtotal,tgtGBdirty,stopflushGB,state"]]}
    },
    'vpcache': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['vpcache', 'datetime,sizeMB']]}
    },
    'onstat-g_prc': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['prc_stats', 'datetime,numlists,pc_poolsize,ref_cnt,dropped,udrentries,entriesinuse']]}
    },
    'lru_k': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['lru_stats', 'datetime,bufsz,dirtynow,tgtpctdirty,dirtypctnow,dirtyGBnow,stopflushGB,state']]}
    },
    'onstat-l': {
        'SUB': import_data_onstat_l,
        'VALUES': {'IMPORT': [['onstat_l', 'datetime,epoch,pbuffer,pbufused,pbufsize,pusedpct,lbuffer,lbufused']]}
    },
    'partition_summary': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [
            ['partition_summary', 'datetime,npages,nused,npdata,nrows,flgs,seqsc,lkrqs,lkwts,ucnt,touts,isrd,iswrt,isrwt,isdel,dlks,bfrd,bfwrt,nextns,area'],
            ['partition_summary', 'datetime,npages,nused,npdata,nrows,flgs,seqsc,lkrqs,lkwts,ucnt,touts,isrd,iswrt,isrwt,isdel,dlks,bfrd,bfwrt,area']
        ]}
    },
    'onstat-g_seg': {
        'SUB': import_data,
        'VALUES': {'IMPORT': [['onstat_g_seg', 'datetime,segs,totalblks,usedbliks,pctused']]}
    },
}

# Function to handle file movement on error
def move_file(indir, outdir, error_folder, file, log):
    source = os.path.join(indir, file)
    destination_dir = os.path.join(outdir)
    os.makedirs(destination_dir, exist_ok=True)
    destination = os.path.join(destination_dir, file)
    shutil.move(source, destination)
    log.debug(f"Moved {file} to {destination_dir}")

# Main function to process files from directory
def produce_import_files(subroutines, indir, config, log, db):
    # Fetch files from the input directory
    try:
        files = os.listdir(indir)
    except Exception as e:
        log.error(f"Failed to read directory {indir}: {e}")
        return

    for file in files:
        file_path = os.path.join(indir, file)
        if not os.path.isfile(file_path):
            continue  # Skip if it's not a file

        # Try to match the file with patterns and extract data
        match = re.match(r"^(\S+?)_(\S+?)_(\d{4}-\d{2}-\d{2})_(.*)", file) or \
                re.match(r"^(\S+?)_(\S+?)_(.*-\d{2}:\d{2}-\d{2}:\d{2})_(.*)", file) or \
                re.match(r"^(\S+?)_(\S+?)_([^\_]+)_(.*)", file)

        if match:
            customer, server, date, filename = match.groups()
            subroutine_key = filename

            # Clean up the filename to match subroutine keys
            subroutine_key = re.sub(r"_for_graph", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+k", "_k", subroutine_key)
            subroutine_key = re.sub(r"_\d+$", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+.log$", "", subroutine_key)
            subroutine_key = re.sub(r".log$", "", subroutine_key)
            print("SUB ", subroutine_key)

            # Check if subroutine exists and call it
            if subroutine_key in subroutines:
                func = subroutines[subroutine_key]['SUB']
                header = subroutines[subroutine_key]['VALUES']['IMPORT'][0][1]
                
                # Execute the function with filename, header, and database
                func(header, file_path, db, customer,server,subroutine_key)
            else:
                log.error(f"No subroutine found for {file}")
                move_file(config.INDIR, config.OUTDIR, 'err', file, log)
        else:
            log.error(f"Errors for {file} no pattern found")
            move_file(config.INDIR, config.OUTDIR, 'err', file, log)
        move_file(config.INDIR, config.OUTDIR, 'err', file, log)

# Execution setup
db = Database()
log = Logger()
config = Config()

produce_import_files(subroutines, config.INDIR, config, log, db)
