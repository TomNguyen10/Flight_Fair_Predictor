import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from multiprocessing import Pool, cpu_count
import itertools


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula."""
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return distance


def get_airport_importance(airport):
    """Calculate airport importance score based on type and hub status."""
    base_score = 1

    # Hub status provides highest importance
    if airport['is_hub']:
        base_score *= 5

    # Airport type multiplier
    if airport['airport_type'] == 'large_airport':
        base_score *= 3

    return base_score


def create_connection_dict(origin_airport, dest_airport, distance, is_international=False):
    """Create a standardized connection dictionary."""
    connection = {
        'origin_airport': origin_airport['iata_code'],
        'origin_name': origin_airport['name'],
        'origin_city': origin_airport['city'],
        'origin_type': origin_airport['airport_type'],
        'origin_is_hub': origin_airport['is_hub'],
        'destination_airport': dest_airport['iata_code'],
        'destination_name': dest_airport['name'],
        'destination_city': dest_airport['city'],
        'destination_type': dest_airport['airport_type'],
        'destination_is_hub': dest_airport['is_hub'],
        'distance_km': round(distance, 2)
    }

    if is_international:
        connection.update({
            'origin_country': origin_airport['country_code'],
            'destination_country': dest_airport['country_code']
        })
    else:
        connection['country'] = origin_airport['country_code']

    return connection


def process_connections_in_parallel(process_func, airports_df, is_international=False):
    """Generic function to process connections in parallel."""
    # Group airports by country
    country_groups = airports_df.groupby('country_code')

    # Prepare arguments for parallel processing
    process_args = [
        (country_code, group, airports_df)
        for country_code, group in country_groups
        if len(group) >= 1  # Process all countries with at least one airport
    ]

    # Use parallel processing to generate connections
    num_cores = max(1, cpu_count() - 1)  # Leave one core free
    print(f"Using {num_cores} CPU cores for parallel processing...")

    with Pool(num_cores) as pool:
        all_connections = pool.map(process_func, process_args)

    # Flatten the list of connections
    connections = list(itertools.chain.from_iterable(all_connections))

    return pd.DataFrame(connections)


def print_connection_statistics(connections_df, is_international=False):
    """Print statistics about the generated connections."""
    print("\nConnection Statistics:")
    print(f"Total connections: {len(connections_df)}")

    if is_international:
        print(
            f"Countries with outgoing connections: {len(connections_df['origin_country'].unique())}")
        print(
            f"Countries with incoming connections: {len(connections_df['destination_country'].unique())}")
    else:
        print(f"Countries covered: {len(connections_df['country'].unique())}")

    # Print top 10 countries by number of connections
    print("\nTop 10 countries by number of connections:")
    country_column = 'origin_country' if is_international else 'country'
    country_stats = connections_df[country_column].value_counts().head(10)
    print(country_stats)

    # Print statistics for major hubs in different continents
    print("\nMajor Hub Statistics:")
    continents = {
        'North America': ['US', 'CA', 'MX'],
        'Europe': ['GB', 'FR', 'DE', 'ES', 'IT', 'NL', 'TR'],
        'Asia': ['CN', 'JP', 'KR', 'IN', 'TH', 'SG', 'ID', 'MY', 'VN', 'AE'],
        'Oceania': ['AU', 'NZ'],
        'South America': ['BR', 'AR', 'CO', 'CL', 'PE'],
        'Africa': ['ZA', 'EG', 'ET', 'KE', 'MA']
    }

    for continent, countries in continents.items():
        print(f"\n{continent} Major Hubs:")
        country_col = 'origin_country' if is_international else 'country'
        continent_hubs = connections_df[
            (connections_df[country_col].isin(countries)) &
            (connections_df['origin_is_hub'] == True)
        ]
        hub_stats = continent_hubs.groupby('origin_airport').agg({
            'destination_airport': 'count',
            country_col: 'first'
        }).sort_values('destination_airport', ascending=False).head(5)

        for idx, row in hub_stats.iterrows():
            print(
                f"{idx} ({row[country_col]}): {row['destination_airport']} connections")


def print_example_connections(connections_df, country_code, is_international=False):
    """Print example connections for a specific country."""
    print(
        f"\nExample {'international' if is_international else 'domestic'} connections from {country_code}:")
    country_col = 'origin_country' if is_international else 'country'
    country_connections = connections_df[connections_df[country_col] == country_code].sample(
        min(10, len(connections_df)))

    for _, conn in country_connections.iterrows():
        if is_international:
            print(f"{conn['origin_airport']} ({conn['origin_city']}) → "
                  f"{conn['destination_airport']} ({conn['destination_city']}, {conn['destination_country']}): "
                  f"{conn['distance_km']}km")
        else:
            print(f"{conn['origin_airport']} ({conn['origin_city']}) ↔ "
                  f"{conn['destination_airport']} ({conn['destination_city']}): "
                  f"{conn['distance_km']}km")
