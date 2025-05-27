import pandas as pd
import numpy as np
from scipy.optimize import minimize

## ---------------------------------------------

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


# ------------------------------


def calculate_portfolio_variance(weights, cov):
    return weights.T @ cov @ weights

def calculate_negative_sharpe_ratio(weights, mu, cov):
    portfolio_return = weights @ mu
    portfolio_volatility = np.sqrt(weights.T @ cov @ weights)
    return -portfolio_volatility/portfolio_return


def calculate_optimized_weights(mu, cov, target_return):

    n_assets = len(mu)

    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        {'type': 'eq', 'fun': lambda w: w @ mu - target_return}
    ]
    bounds = [(0, 1) for _ in range(n_assets)] # Long-only constraint
    initial_weights = np.ones(n_assets) / n_assets

    result = minimize(
        calculate_portfolio_variance,
        initial_weights,
        args=(cov, ),
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )

    if result.success:
        optimal_weights = result.x
    else:
        error_message = f"Optimization failed: {result.message}" #TODO: handle error
        optimal_weights = None

    return optimal_weights