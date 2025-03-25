import pandas as pd
from airport_utils import (
    calculate_distance,
    create_connection_dict,
    process_connections_in_parallel,
    print_connection_statistics,
    print_example_connections
)


def is_valid_connection(origin_airport, dest_airport, distance):
    """Determine if a connection is valid based on logical criteria."""
    # Skip if either airport is missing coordinates
    if pd.isna(origin_airport['latitude']) or pd.isna(origin_airport['longitude']) or \
       pd.isna(dest_airport['latitude']) or pd.isna(dest_airport['longitude']):
        return False

    # Maximum realistic flight distance (km) - based on longest commercial flights
    MAX_DISTANCE = 15000  # Example: New York to Singapore is about 15,000 km

    # Skip if distance is too long
    if distance > MAX_DISTANCE:
        return False

    # For non-hub airports, limit connections to 8000km unless connecting to a hub
    if not origin_airport['is_hub']:
        if not dest_airport['is_hub'] and distance > 8000:
            return False

    return True


def process_country_airports(args):
    """Process international connections for a single country."""
    country_code, country_airports_df, all_airports_df = args
    connections = []

    # Create a set to track processed airport pairs
    processed_pairs = set()

    # Get international airports for the current country (only hubs and large airports that handle international flights)
    international_airports = country_airports_df[
        (country_airports_df['is_hub']) |
        (country_airports_df['airport_type'] == 'large_airport')
    ]

    # Get international airports from other countries
    other_countries_airports = all_airports_df[
        (all_airports_df['country_code'] != country_code) &
        ((all_airports_df['is_hub']) |
         (all_airports_df['airport_type'] == 'large_airport'))
    ]

    # Process each international airport in the country
    for idx, origin_airport in international_airports.iterrows():
        # Calculate distances to all international airports in other countries
        other_countries_airports['distance'] = other_countries_airports.apply(
            lambda x: calculate_distance(
                origin_airport['latitude'], origin_airport['longitude'],
                x['latitude'], x['longitude']
            ),
            axis=1
        )

        # Filter airports based on distance and logical criteria
        valid_airports = other_countries_airports[
            other_countries_airports.apply(
                lambda x: is_valid_connection(
                    origin_airport, x, x['distance']),
                axis=1
            )
        ]

        # Sort by importance (hub status and distance)
        valid_airports = valid_airports.sort_values(
            ['is_hub', 'distance'],
            ascending=[False, True]
        )

        # Add connections to the list
        for _, dest in valid_airports.iterrows():
            # Create a unique identifier for this airport pair
            pair_id = tuple(
                sorted([origin_airport['iata_code'], dest['iata_code']]))

            # Only process if we haven't seen this pair before
            if pair_id not in processed_pairs:
                # Add the connection using the shared utility function
                connections.append(create_connection_dict(
                    origin_airport, dest, dest['distance'], is_international=True))
                processed_pairs.add(pair_id)

    return connections


def create_international_connections(airports_df):
    """Create international flight connections using parallel processing."""
    return process_connections_in_parallel(process_country_airports, airports_df, is_international=True)


def main():
    # Read the airports data
    print("Reading airports data...")
    airports_df = pd.read_csv('data/airports.csv')

    print("Generating international flight connections...")
    connections_df = create_international_connections(airports_df)

    # Save to CSV
    output_file = 'data/international_connections.csv'
    connections_df.to_csv(output_file, index=False)
    print(f"International connections saved to {output_file}")

    # Print statistics using shared utility function
    print_connection_statistics(connections_df, is_international=True)

    # Print example connections for Vietnam using shared utility function
    print_example_connections(connections_df, 'VN', is_international=True)


if __name__ == "__main__":
    main()
