import pandas as pd
from airport_utils import (
    calculate_distance,
    create_connection_dict,
    process_connections_in_parallel,
    print_connection_statistics,
    print_example_connections
)


def is_valid_domestic_connection(origin_airport, dest_airport, distance):
    """Determine if a domestic connection is valid based on logical criteria."""
    # Skip if either airport is missing coordinates
    if pd.isna(origin_airport['latitude']) or pd.isna(origin_airport['longitude']) or \
       pd.isna(dest_airport['latitude']) or pd.isna(dest_airport['longitude']):
        return False

    # Maximum realistic domestic flight distance (km)
    MAX_DOMESTIC_DISTANCE = 5000  # Example: New York to Los Angeles is about 4,000 km

    # Skip if distance is too long
    if distance > MAX_DOMESTIC_DISTANCE:
        return False

    # For small airports, only allow connections to hubs or large airports
    if origin_airport['airport_type'] == 'small_airport':
        if not (dest_airport['is_hub'] or dest_airport['airport_type'] == 'large_airport'):
            # For small airports, limit connections to 1000km unless to a hub
            if distance > 1000:
                return False

    # For medium airports, allow more connections but still with some restrictions
    if origin_airport['airport_type'] == 'medium_airport':
        if not (dest_airport['is_hub'] or dest_airport['airport_type'] == 'large_airport'):
            # For medium airports, limit connections to 2000km unless to a hub
            if distance > 2000:
                return False

    return True


def process_country_airports(args):
    """Process domestic connections for a single country."""
    country_code, country_airports_df, _ = args
    connections = []

    # Create a set to track processed airport pairs
    processed_pairs = set()

    # Process each airport in the country
    for idx, origin_airport in country_airports_df.iterrows():
        # Get other airports in the same country
        domestic_airports = country_airports_df[country_airports_df.index != idx].copy(
        )

        # Calculate distances to all other domestic airports
        domestic_airports['distance'] = domestic_airports.apply(
            lambda x: calculate_distance(
                origin_airport['latitude'], origin_airport['longitude'],
                x['latitude'], x['longitude']
            ),
            axis=1
        )

        # Filter airports based on distance and logical criteria
        valid_airports = domestic_airports[
            domestic_airports.apply(
                lambda x: is_valid_domestic_connection(
                    origin_airport, x, x['distance']),
                axis=1
            )
        ]

        # Sort by importance (hub status, airport type, and distance)
        valid_airports = valid_airports.sort_values(
            ['is_hub', 'airport_type', 'distance'],
            ascending=[False, True, True]
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
                    origin_airport, dest, dest['distance'], is_international=False))
                processed_pairs.add(pair_id)

    return connections


def create_domestic_connections(airports_df):
    """Create domestic flight connections using parallel processing."""
    return process_connections_in_parallel(process_country_airports, airports_df, is_international=False)


def main():
    # Read the airports data
    print("Reading airports data...")
    airports_df = pd.read_csv('data/airports.csv')

    print("Generating domestic flight connections...")
    connections_df = create_domestic_connections(airports_df)

    # Save to CSV
    output_file = 'data/domestic_connections.csv'
    connections_df.to_csv(output_file, index=False)
    print(f"Domestic connections saved to {output_file}")

    # Print statistics using shared utility function
    print_connection_statistics(connections_df, is_international=False)

    # Print example connections for Vietnam using shared utility function
    print_example_connections(connections_df, 'VN', is_international=False)


if __name__ == "__main__":
    main()
