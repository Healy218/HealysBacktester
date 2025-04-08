# data_preprocessing.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def prepare_nn_data(df, target_column, test_size=0.2):
    """
    Prepares data for training and testing a neural network.
    """
    # Select features and target variable
    # Split data into training and testing sets
    # Scale numerical features
    return X_train, X_test, y_train, y_test