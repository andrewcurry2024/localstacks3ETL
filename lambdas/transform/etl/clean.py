import pandas as pd

def convert_numeric_columns_to_float(df):
    """
    Convert all numeric columns in a DataFrame to float.

    Parameters:
        df (pd.DataFrame): The DataFrame to process.

    Returns:
        pd.DataFrame: The DataFrame with numeric columns converted to float.
    """
    # Select numeric columns and convert them to float
    numeric_cols = df.select_dtypes(include=['number']).columns
    df[numeric_cols] = df[numeric_cols].astype(float)
    return df

def clean_data(df: pd.DataFrame, header: str, customer: str, server: str, sub_key: str, digits) -> pd.DataFrame:
    df = df.copy()
    for column in df.columns:
        if column not in ['datetime', 'customer', 'server']:
            condition_large_value = (df[column].apply(lambda x: isinstance(x, (int, float)) and x > 9023372036854775800))
            condition_nan = (df[column].apply(lambda x: isinstance(x, str) and x.lower() == 'nan'))
            df.loc[condition_large_value, column] = -1
            df.loc[condition_nan, column] = -1

    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
    else:
        if 'date' in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
            df.drop(columns=['date', 'time'], inplace=True)
        else:
            print("ERROR: No 'datetime', 'date', or 'time' columns found!")

    if 'datetime' in df.columns:
        cols = ['datetime'] + [col for col in df.columns if col != 'datetime']
        df = df[cols]
    else:
        print("ERROR: 'datetime' column not found!")

    header_columns = header.split(',')

    if len(header_columns) < len(df.columns):
        df = df.iloc[:, :len(header_columns)]

    if len(header_columns) == len(df.columns):
        df.columns = header_columns
    else:
        print(f"ERROR: Column count mismatch: header has {len(header_columns)} columns, but dataframe has {len(df.columns)} columns.")

    df.loc[:, 'customer'] = customer
    df.loc[:, 'server'] = server
    df.loc[:, '_measurement'] = sub_key
    df.loc[:, 'digits'] = digits

    df = convert_numeric_columns_to_float(df)

    print(f"Cleaned Data Overview for {customer}-{server}:")
    print(df.info())
    return df
