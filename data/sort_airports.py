#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script sorts airport data from a CSV file by country in alphabetical order.
Within each country, international airports are prioritized over domestic ones.
The result is saved to a new CSV file.
"""

import pandas as pd
import os


def read_airports_data(file_path='airports.csv'):
    """
    Read the airports CSV file into a pandas DataFrame.

    Parameters:
    -----------
    file_path : str
        Path to the airports CSV file.

    Returns:
    --------
    pandas.DataFrame
        DataFrame containing the airports data.
    """
    # Get the absolute path if a relative path is provided
    if not os.path.isabs(file_path):
        # Check if the file is in the current directory or in the data directory
        if os.path.exists(file_path):
            abs_file_path = os.path.abspath(file_path)
        elif os.path.exists(os.path.join('data', file_path)):
            abs_file_path = os.path.abspath(os.path.join('data', file_path))
        else:
            raise FileNotFoundError(f"Could not find {file_path}")
    else:
        abs_file_path = file_path

    # Read the CSV file
    df = pd.read_csv(abs_file_path)
    print(f"Read {len(df)} airports from {abs_file_path}")
    return df


def is_international_airport(name):
    """
    Determine if an airport is international based on its name.

    Parameters:
    -----------
    name : str
        The name of the airport.

    Returns:
    --------
    bool
        True if the airport is international, False otherwise.
    """
    return 'international' in name.lower()


def sort_airports(df):
    """
    Sort airports by country alphabetically, and within each country
    prioritize international airports over domestic ones.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the airports data.

    Returns:
    --------
    pandas.DataFrame
        Sorted DataFrame.
    """
    # Create a new column indicating if the airport is international
    df['is_international'] = df['name'].apply(is_international_airport)

    # Sort by country_id (alphabetically) and is_international (descending)
    sorted_df = df.sort_values(by=['country_id', 'is_international'],
                               ascending=[True, False])

    # Drop the temporary column
    sorted_df = sorted_df.drop(columns=['is_international'])

    return sorted_df


def save_sorted_airports(df, output_file='sorted_airports.csv'):
    """
    Save the sorted airports to a CSV file.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the sorted airports data.
    output_file : str
        Path to save the sorted data.
    """
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # If output_file is not an absolute path, make it relative to the script directory
    if not os.path.isabs(output_file):
        output_file = os.path.join(script_dir, output_file)

    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Saved sorted airports to {output_file}")


def main():
    """
    Main function to run the script.
    """
    # Read the airports data
    airports_df = read_airports_data()

    # Sort the airports
    sorted_airports = sort_airports(airports_df)

    # Save the sorted data
    save_sorted_airports(sorted_airports)

    # Print some statistics
    print(f"\nTotal airports: {len(sorted_airports)}")
    # Count international airports
    international_count = sorted_airports['name'].apply(
        is_international_airport).sum()
    print(f"International airports: {international_count}")
    print(f"Domestic airports: {len(sorted_airports) - international_count}")

    # Count airports by country
    country_counts = sorted_airports['country_id'].value_counts()
    print("\nTop 10 countries by number of airports:")
    print(country_counts.head(10))

    return sorted_airports


if __name__ == "__main__":
    sorted_airports = main()

    # Example: Display the first few airports from a specific country
    # This is just for demonstration, you can modify or remove this part
    country_code = 'US'  # Change this to view airports from a different country
    country_airports = sorted_airports[sorted_airports['country_id']
                                       == country_code]

    print(f"\nFirst 5 airports in {country_code} (international first):")
    print(country_airports.head(5)[['code', 'name', 'city']])
