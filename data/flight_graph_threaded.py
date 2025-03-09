#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Multi-threaded implementation for generating flight connection graphs.
This script distributes the workload of checking flight connections across multiple threads,
making it suitable for running in GitHub Actions or other CI/CD environments.
"""

import pandas as pd
import os
import csv
import time
import json
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timedelta
from fast_flights import FlightData, Passengers, Result, get_flights

# Maximum number of worker threads to use
# Adjust based on the environment - GitHub Actions typically has 2 cores
MAX_WORKERS = 4

# Maximum API requests per minute to avoid rate limiting
# Adjust based on the API's rate limits
MAX_REQUESTS_PER_MINUTE = 60

# Semaphore to control API request rate
api_semaphore = threading.Semaphore(MAX_REQUESTS_PER_MINUTE)
# Lock for thread-safe access to shared resources
results_lock = threading.Lock()

#####################################################################
# Core Functions (Independent of Multithreading)
#####################################################################


def load_airports_data(file_path='airports.csv'):
    """Load the sorted airports data from CSV file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.isabs(file_path):
        file_path = os.path.join(script_dir, file_path)

    return pd.read_csv(file_path)


def get_international_airports(df):
    """Extract international airports from the dataframe."""
    return df[df['name'].str.contains('International', case=False)]


def group_airports_by_country(df):
    """Group airports by country."""
    country_groups = {}
    for country, group in df.groupby('country_id'):
        country_groups[country] = group

    return country_groups


def create_airport_pairs(airports):
    """Create all possible pairs of airports for checking direct flights."""
    airport_codes = airports['code'].tolist() if isinstance(
        airports, pd.DataFrame) else airports
    pairs = []

    for i, origin in enumerate(airport_codes):
        for destination in airport_codes[i+1:]:
            pairs.append((origin, destination))

    return pairs


def check_direct_flights(origin_code, destination_code, max_retries=3, delay=2):
    """Check if there are direct flights between two airports."""
    future_dates = [(datetime.now() + timedelta(days=i)
                     ).strftime("%Y-%m-%d") for i in range(30, 35)]

    for current_date in future_dates:
        for attempt in range(max_retries):
            try:
                result = get_flights(
                    flight_data=[
                        FlightData(
                            date=current_date, from_airport=origin_code, to_airport=destination_code)
                    ],
                    trip="one-way",
                    seat="economy",
                    passengers=Passengers(
                        adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
                    fetch_mode="fallback",
                )

                if result and result.flights:
                    for flight in result.flights:
                        if flight.stops == 0:
                            return True

                # API responded but no direct flights found
                break

            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(delay)

    # No direct flights found
    return False


def process_airport_pairs(pairs):
    """Process a list of airport pairs and find direct connections.

    This is the core logic function without threading.

    Parameters:
    -----------
    pairs : list
        List of tuples containing (origin_code, destination_code) pairs

    Returns:
    --------
    dict
        Dictionary with origin airport codes as keys and lists of 
        directly connected destinations as values
    """
    connections = defaultdict(list)

    for origin, destination in pairs:
        if check_direct_flights(origin, destination):
            connections[origin].append(destination)

    return dict(connections)


def process_country_airports(country_code, country_df):
    """Process airports within a single country (core logic without threading).

    Parameters:
    -----------
    country_code : str
        Country code to process
    country_df : pandas.DataFrame
        DataFrame containing airports for this country

    Returns:
    --------
    dict
        Dictionary with airport codes as keys and lists of directly connected
        airports as values
    """
    # Generate all possible pairs of airports in this country
    pairs = create_airport_pairs(country_df)

    # Process the pairs to find direct connections
    return process_airport_pairs(pairs)


def process_international_airports(int_airports_df):
    """Process international airports (core logic without threading).

    Parameters:
    -----------
    int_airports_df : pandas.DataFrame
        DataFrame containing international airports

    Returns:
    --------
    dict
        Dictionary with international airport codes as keys and lists of directly
        connected international airports as values
    """
    # Generate all possible pairs of international airports
    pairs = create_airport_pairs(int_airports_df)

    # Process the pairs to find direct connections
    connections = process_airport_pairs(pairs)

    # Also check the reverse direction (if A->B exists, B->A might not)
    reverse_pairs = [(dest, orig)
                     for orig in connections for dest in connections[orig]]
    reverse_connections = process_airport_pairs(reverse_pairs)

    # Merge the connections
    for origin, destinations in reverse_connections.items():
        if origin not in connections:
            connections[origin] = destinations
        else:
            for dest in destinations:
                if dest not in connections[origin]:
                    connections[origin].append(dest)

    return connections


def save_connections_to_csv(connections, output_file, airport_df):
    """Save airport connections to a CSV file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.isabs(output_file):
        output_file = os.path.join(script_dir, output_file)

    # Create mappings for airport names and countries
    airport_names = dict(zip(airport_df['code'], airport_df['name']))
    airport_countries = dict(zip(airport_df['code'], airport_df['country_id']))

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(['origin_code', 'origin_name', 'origin_country',
                         'destination_code', 'destination_name', 'destination_country'])

        # Write connections
        for origin, destinations in connections.items():
            origin_name = airport_names.get(origin, "Unknown Airport")
            origin_country = airport_countries.get(origin, "Unknown Country")

            for dest in destinations:
                dest_name = airport_names.get(dest, "Unknown Airport")
                dest_country = airport_countries.get(dest, "Unknown Country")
                writer.writerow([origin, origin_name, origin_country,
                                 dest, dest_name, dest_country])


def save_json_results(connections, filename):
    """Save connections to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(connections, f)

#####################################################################
# Multithreading Implementation
#####################################################################


def distribute_workload(items, num_workers):
    """Distribute workload evenly across workers.

    Parameters:
    -----------
    items : list
        List of items to distribute (either countries or airport pairs)
    num_workers : int
        Number of worker threads to distribute to

    Returns:
    --------
    list
        List of batches, where each batch is a list of items
    """
    # Ensure we don't create more batches than items
    num_workers = min(num_workers, len(items))

    # Calculate batch size
    batch_size = len(items) // num_workers
    remainder = len(items) % num_workers

    batches = []
    start_idx = 0

    for i in range(num_workers):
        # Add one more item to the first 'remainder' batches to handle uneven divisions
        current_batch_size = batch_size + (1 if i < remainder else 0)
        end_idx = start_idx + current_batch_size

        batches.append(items[start_idx:end_idx])
        start_idx = end_idx

    return batches


def process_batch_thread_safe(pairs_batch, batch_id=0):
    """Process a batch of airport pairs with thread safety.

    This is a wrapper around the core process_airport_pairs function
    that adds thread safety and rate limiting.

    Parameters:
    -----------
    pairs_batch : list
        List of tuples containing (origin_code, destination_code) pairs
    batch_id : int
        ID of the batch for tracking purposes

    Returns:
    --------
    dict
        Dictionary with origin airport codes as keys and lists of directly
        connected destinations as values
    """
    connections = defaultdict(list)
    processed_count = 0
    total_pairs = len(pairs_batch)

    for origin, destination in pairs_batch:
        # Use semaphore to control API request rate
        with api_semaphore:
            if check_direct_flights(origin, destination):
                with results_lock:
                    connections[origin].append(destination)

        processed_count += 1
        if processed_count % 10 == 0:
            completion = (processed_count / total_pairs) * 100
            # This could be replaced with a progress reporter in GitHub Actions
            pass

    return dict(connections)


def process_country_airports_threaded(country_data, num_workers=MAX_WORKERS):
    """Process all airports within countries using multiple threads.

    Parameters:
    -----------
    country_data : dict
        Dictionary with country codes as keys and DataFrames of airports as values
    num_workers : int
        Number of worker threads to use

    Returns:
    --------
    dict
        Dictionary with airport codes as keys and lists of connected destinations
    """
    # Create a list of country codes
    country_codes = list(country_data.keys())

    # Distribute countries across workers
    country_batches = distribute_workload(country_codes, num_workers)

    all_results = {}

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_batch = {}

        for batch_id, country_batch in enumerate(country_batches):
            # Define a worker function for each batch
            def process_country_batch(batch_countries, batch_id):
                batch_results = {}

                for country_code in batch_countries:
                    country_df = country_data[country_code]

                    # Call the core logic function
                    country_connections = process_country_airports(
                        country_code, country_df)

                    # Save the connections for this country
                    save_json_results(country_connections,
                                      f"flight_connections_{country_code}.json")

                    # Add to batch results
                    batch_results.update(country_connections)

                return batch_results

            # Submit the batch
            future = executor.submit(
                process_country_batch, country_batch, batch_id)
            future_to_batch[future] = batch_id

        # Collect results as they complete
        for future in as_completed(future_to_batch):
            batch_id = future_to_batch[future]
            try:
                batch_results = future.result()
                all_results.update(batch_results)
            except Exception as e:
                # Log the error but continue processing
                pass

    return all_results


def process_international_airports_threaded(int_airports_df, num_workers=MAX_WORKERS):
    """Process international airports using multiple threads.

    Parameters:
    -----------
    int_airports_df : pandas.DataFrame
        DataFrame containing international airports
    num_workers : int
        Number of worker threads to use

    Returns:
    --------
    dict
        Dictionary with airport codes as keys and lists of connected destinations
    """
    # This could be optimized to directly call the core function if small enough
    if len(int_airports_df) <= 5:  # Arbitrary small number
        return process_international_airports(int_airports_df)

    # Generate all possible pairs of international airports
    all_pairs = create_airport_pairs(int_airports_df)

    # Distribute pairs across workers
    pair_batches = distribute_workload(all_pairs, num_workers)

    all_results = defaultdict(list)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []

        for batch_id, pairs_batch in enumerate(pair_batches):
            future = executor.submit(
                process_batch_thread_safe, pairs_batch, batch_id)
            futures.append(future)

        # Collect results as they complete
        for future in as_completed(futures):
            try:
                batch_results = future.result()

                # Merge results
                with results_lock:
                    for origin, destinations in batch_results.items():
                        all_results[origin].extend(destinations)
            except Exception as e:
                # Log the error but continue processing
                pass

    # Save the international connections to a file
    save_json_results(dict(all_results),
                      "flight_connections_international.json")

    return dict(all_results)

#####################################################################
# Main Function and Entry Point
#####################################################################


def run_single_threaded():
    """Run the flight connection analysis in single-threaded mode.

    This function runs the core logic without multithreading.
    Useful for testing or smaller datasets.

    Returns:
    --------
    dict
        Dictionary with all the connection results
    """
    # Load data
    airports_df = load_airports_data()

    # Get international airports
    int_airports_df = get_international_airports(airports_df)

    # Group airports by country
    country_groups = group_airports_by_country(airports_df)

    # Process domestic routes by country
    domestic_connections = {}
    for country_code, country_df in country_groups.items():
        country_connections = process_country_airports(
            country_code, country_df)
        domestic_connections.update(country_connections)

        # Save country-specific connections
        save_json_results(country_connections,
                          f"flight_connections_{country_code}.json")

    # Process international routes
    international_connections = process_international_airports(int_airports_df)

    # Save international connections
    save_json_results(international_connections,
                      "flight_connections_international.json")

    # Combine all connections
    all_connections = {}
    all_connections.update(domestic_connections)
    all_connections.update(international_connections)

    # Save all connections to CSV
    save_connections_to_csv(
        all_connections, "flight_connections_all.csv", airports_df)

    return {
        'domestic': domestic_connections,
        'international': international_connections,
        'all': all_connections
    }


def main():
    """Main function to orchestrate the multi-threaded processing."""
    # Load data
    airports_df = load_airports_data()
    # Get international airports
    int_airports_df = get_international_airports(airports_df)

    # Group airports by country
    country_groups = group_airports_by_country(airports_df)

    # Process domestic routes by country (multi-threaded)
    domestic_connections = process_country_airports_threaded(country_groups)

    # Process international routes (multi-threaded)
    international_connections = process_international_airports_threaded(
        int_airports_df)

    # Combine all connections
    all_connections = {}
    all_connections.update(domestic_connections)
    all_connections.update(international_connections)

    # Save all connections to CSV
    save_connections_to_csv(
        all_connections, "flight_connections_all.csv", airports_df)

    return {
        'domestic': domestic_connections,
        'international': international_connections,
        'all': all_connections
    }


if __name__ == "__main__":
    # Use multithreaded version by default
    use_multithreading = True

    try:
        if use_multithreading:
            results = main()
        else:
            results = run_single_threaded()

        # Report completion status
        with open("flight_connections_summary.json", "w") as f:
            summary = {
                "domestic_connections": sum(len(dests) for dests in results['domestic'].values()),
                "international_connections": sum(len(dests) for dests in results['international'].values()),
                "total_connections": sum(len(dests) for dests in results['all'].values()),
                "completion_time": datetime.now().isoformat(),
                "multithreaded": use_multithreading
            }
            json.dump(summary, f, indent=2)
    except Exception as e:
        # Log the error and exit
        with open("flight_connections_error.log", "w") as f:
            f.write(f"Error: {str(e)}")
        exit(1)
