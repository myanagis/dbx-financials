import pandas as pd


def calculate_covariance_matrix(monthly_returns_df, type="standard"):
    """
    Calculates the covariance matrix of a time series of returns.

    Args:
        monthly_returns_df (DataFrame): Dataframe of monthly returns.
        type                     (str): Type of covariance to calculate, either "standard" (default) 
                                        or "ewma" (weighted half-life, with half life of 60 months)

    Returns:
        DataFrame: annualized covariance matrix of input returns
    """
    monthly_cov_matrix = pd.DataFrame()

    # "Standard" covariance
    if type == "standard":
        monthly_cov_matrix = monthly_returns_df.cov() 
    
    # EWMA covariance using half-life
    elif type == "ewma":
        half_life = 60
        ewma_lambda = 0.5 ** (1 / half_life)
        alpha = 1 - ewma_lambda

        # Compute EWMA covariance
        # This returns a MultiIndex DataFrame: index is (time, asset1), columns are asset2
        ewma_cov = monthly_returns_df.ewm(alpha=alpha, adjust=False).cov(pairwise=True)

        # Get the most recent (last date's) covariance matrix
        last_timestamp = monthly_returns_df.index[-1]
        monthly_cov_matrix = ewma_cov.loc[last_timestamp]

    else:
        raise ValueError("Invalid type. Choose 'standard' or 'ewma'.")

    # Annualize the covariance matrix (monthly → annual)
    return 12 * monthly_cov_matrix
