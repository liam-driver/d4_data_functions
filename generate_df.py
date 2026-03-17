import pandas as pd
from safe_div import safe_div

def get_total_row(df, period_label, dim_cols=2):
    # Initialise the total row as a dictionary
    total_row = {
        df.columns[0]: period_label,
        df.columns[1]: "Total",
        **df.iloc[:, dim_cols:].sum(numeric_only=True).to_dict()
    }
    # Return the dicitonary concated on the end of the dataframe
    return pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

# Email Data for Paid Ecomm
def paid_ecommerce(df, breakdown_dimension, table_type):
    headers = list(df.columns.values)
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[11], headers[13]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)    

    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Cost',
        numeric_headers[1]: 'Transaction Revenue'
        })

    # Get Secondary Metrics
    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    return(df_grouped)

# Email Data for Paid Lead Gen
def paid_lead_gen(df, breakdown_dimension, table_type):
    # Group, filter and clean Dataframes
    headers = list(df.columns.values)
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[11], headers[12]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Cost',
        numeric_headers[1]: 'Conversions',
        })

    # Get Secondary Metrics
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )
    return(df_grouped)

# Paid Search Ecommerce
def paid_search_ecommerce(df, breakdown_dimension, headers, table_type):
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13], headers[14], headers[15], headers[16]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Transactions',
        numeric_headers[4]: 'Transaction Revenue'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Clicks'],
        multiplier = 100
    )

    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )
    df_grouped['Impression Share'] = safe_div(
        df_grouped['Search Impressions'],
        df_grouped['Total Eligible Impressions – Estimated'],
        multiplier = 100
    )
    df_grouped['Abs. Top Impression Share'] = safe_div(
        df_grouped['Total Absolute Top Impressions'],
        df_grouped['Search Impressions'],
        multiplier = 100
    )

    return(df_grouped)

# Paid Search Lead Gen
def paid_search_lead_gen(df, breakdown_dimension, headers, table_type):
    # Group, filter and clean Dataframes
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13], headers[14], headers[15]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Conversions'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )
    df_grouped['Impression Share'] = safe_div(
        df_grouped['Search Impressions'],
        df_grouped['Total Eligible Impressions – Estimated'],
        multiplier = 100
    )
    df_grouped['Abs. Top Impression Share'] = safe_div(
        df_grouped['Total Absolute Top Impressions'],
        df_grouped['Search Impressions'],
        multiplier = 100
    )
    return(df_grouped)

# Paid Shopping Ecommerce
def paid_shopping_ecommerce(df, breakdown_dimension, headers, table_type):
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13], headers[14], headers[15]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Transactions',
        numeric_headers[4]: 'Transaction Revenue'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Clicks'],
        multiplier = 100
    )

    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )
    df_grouped['Impression Share'] = safe_div(
        df_grouped['Search Impressions'],
        df_grouped['Total Eligible Impressions – Estimated'],
        multiplier = 100
    )
    return(df_grouped)

# Paid Shopping Lead Gen
def paid_shopping_lead_gen(df, breakdown_dimension, headers, table_type): 
    # Group, filter and clean Dataframes
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Conversions'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )

    return(df_grouped)

# Paid Video Lead gen
def paid_video_lead_gen(df, breakdown_dimension, headers, table_type):
    # Group, filter and clean Dataframes
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[16], headers[17], headers[18]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Conversions',
        numeric_headers[4]: 'Views',
        numeric_headers[5]: 'Hooks',
        numeric_headers[6]: 'Holds'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )
    df_grouped['View Rate'] = safe_div(
        df_grouped['Views'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['Hook Rate'] = safe_div(
        df_grouped['Hooks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['Hold Rate'] = safe_div(
        df_grouped['Holds'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    return(df_grouped)

# Paid Video Ecommerce
def paid_video_ecommerce(df, breakdown_dimension, headers, table_type):
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13], headers[17],headers[18],headers[19]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Transactions',
        numeric_headers[4]: 'Transaction Revenue',
        numeric_headers[5]: 'Views',
        numeric_headers[6]: 'Hooks',
        numeric_headers[7]: 'Holds'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Clicks'],
        multiplier = 100
    )

    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )

    df_grouped['View Rate'] = safe_div(
        df_grouped['Views'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['Hook Rate'] = safe_div(
        df_grouped['Hooks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['Hold Rate'] = safe_div(
        df_grouped['Holds'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    return(df_grouped)

# Paid Display Lead gen
def paid_display_lead_gen(df, breakdown_dimension, headers, table_type):
    # Group, filter and clean Dataframes
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Conversions'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )
    return(df_grouped)

# Paid Display Ecommerce
def paid_display_ecommerce(df, breakdown_dimension, headers, table_type):
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Transactions',
        numeric_headers[4]: 'Transaction Revenue'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Clicks'],
        multiplier = 100
    )

    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )
    return(df_grouped)

# Paid Social Video Lead gen
def paid_social_video_lead_gen(df, breakdown_dimension, headers, table_type):
    # Group, filter and clean Dataframes
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[17], headers[18]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Conversions',
        numeric_headers[4]: 'Hooks',
        numeric_headers[5]: 'Holds'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )
    df_grouped['Hook Rate'] = safe_div(
        df_grouped['Hooks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['Hold Rate'] = safe_div(
        df_grouped['Holds'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    return(df_grouped)

# Paid Social Video Ecommerce
def paid_social_video_ecommerce(df, breakdown_dimension, headers, table_type):
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13], headers[18], headers[19]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Transactions',
        numeric_headers[4]: 'Transaction Revenue',
        numeric_headers[5]: 'Hooks',
        numeric_headers[6]: 'Holds'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Clicks'],
        multiplier = 100
    )

    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )
    df_grouped['Hook Rate'] = safe_div(
        df_grouped['Hooks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['Hold Rate'] = safe_div(
        df_grouped['Holds'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    return(df_grouped)

# Paid Social Static Lead gen
def paid_social_static_lead_gen(df, breakdown_dimension, headers, table_type):
    # Group, filter and clean Dataframes
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost'})

    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)   
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Conversions'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['CPA'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Conversions'],
        multiplier = 1
    )
    return(df_grouped)

# Paid Social Static Ecommerce
def paid_social_static_ecommerce(df, breakdown_dimension, headers, table_type):
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[9], headers[10], headers[11], headers[12], headers[13]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={"Cost (GBP)": 'Cost','Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Impressions',
        numeric_headers[1]: 'Clicks',
        numeric_headers[2]: 'Cost',
        numeric_headers[3]: 'Transactions',
        numeric_headers[4]: 'Transaction Revenue'
        })

    # Get Secondary Metrics
    df_grouped['CTR'] = safe_div(
        df_grouped['Clicks'],
        df_grouped['Impressions'],
        multiplier = 100
    )
    df_grouped['CPC'] = safe_div(
        df_grouped['Cost'],
        df_grouped['Clicks'],
        multiplier = 1
    ) 
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Clicks'],
        multiplier = 100
    )
    df_grouped['ROAS'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Cost'],
        multiplier = 100
    )
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )
    return(df_grouped)

def overall_ecommerce(df, breakdown_dimension, table_type):
    # Group, filter and clean Dataframes
    headers = list(df.columns.values)
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[8], headers[12], headers[13]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={'Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Sessions',
        numeric_headers[1]: 'Transactions',
        numeric_headers[2]: 'Transaction Revenue'
        })
    # Get Secondary Metrics
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Transactions'],
        df_grouped['Sessions'],
        multiplier = 100
    )
    
    df_grouped['AOV'] = safe_div(
        df_grouped['Transaction Revenue'],
        df_grouped['Transactions'],
        multiplier = 1
    )

    return(df_grouped)

def overall_lead_gen(df, breakdown_dimension, table_type):
    # Group, filter and clean Dataframes
    headers = list(df.columns.values)
    headers = [breakdown_dimension[1], breakdown_dimension[0], headers[8], headers[12]]
    numeric_headers = headers[2:]
    df_grouped = df[headers].copy()
    df_grouped[numeric_headers] = df_grouped[numeric_headers].apply(pd.to_numeric, errors="coerce")
    df_grouped = df_grouped.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()
    df_grouped = df_grouped.rename(columns={'Transaction Revenue (GBP)': 'Transaction Revenue'})
    
    # Add a total row for each period
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        curr_df = get_total_row(df_grouped[df_grouped["Period"].eq("Current")].copy(), "Current")
        prev_df = get_total_row(df_grouped[df_grouped["Period"].eq("Previous")].copy(), "Previous")
        df_grouped = pd.concat([curr_df, prev_df], ignore_index=True)
    
    # Standardise Column Names
    df_grouped = df_grouped.rename(columns={
        numeric_headers[0]: 'Sessions',
        numeric_headers[1]: 'Conversions',
        })
    # Get Secondary Metrics
    df_grouped['Conversion Rate'] = safe_div(
        df_grouped['Conversions'],
        df_grouped['Sessions'],
        multiplier = 100
    )
    return(df_grouped)