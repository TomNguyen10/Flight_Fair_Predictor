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


# Define major global hubs with their expected domestic connection counts
MAJOR_GLOBAL_HUBS = {
    # North America
    'US': {
        'JFK': 39, 'ATL': 45, 'ORD': 45, 'DFW': 45, 'LAX': 42, 'DEN': 40,
        'CLT': 38, 'LAS': 35, 'MIA': 35, 'PHX': 35, 'IAH': 38, 'SEA': 35,
        'EWR': 35, 'SFO': 35, 'MSP': 35, 'DTW': 35, 'BOS': 35
    },
    'CA': {'YYZ': 30, 'YVR': 25, 'YUL': 25},
    'MX': {'MEX': 35, 'GDL': 25, 'MTY': 25},

    # Europe
    'GB': {'LHR': 25, 'MAN': 20, 'EDI': 15},
    'FR': {'CDG': 30, 'ORY': 25, 'NCE': 20},
    'DE': {'FRA': 30, 'MUC': 25, 'BER': 20},
    'ES': {'MAD': 30, 'BCN': 25},
    'IT': {'FCO': 25, 'MXP': 20},
    'NL': {'AMS': 20},
    'TR': {'IST': 35, 'AYT': 25, 'ESB': 20},

    # Asia
    'CN': {
        'PEK': 45, 'PVG': 40, 'CAN': 35, 'CTU': 30, 'SZX': 30,
        'KMG': 25, 'XIY': 25, 'CKG': 25, 'HGH': 25
    },
    'JP': {'HND': 35, 'NRT': 30, 'ITM': 25, 'CTS': 20},
    'KR': {'ICN': 25, 'GMP': 20},
    'IN': {'DEL': 40, 'BOM': 35, 'BLR': 30, 'HYD': 25, 'MAA': 25},
    'TH': {'BKK': 30, 'DMK': 25},
    'SG': {'SIN': 15},
    'ID': {'CGK': 35, 'DPS': 25},
    'MY': {'KUL': 25},
    'VN': {'HAN': 20, 'SGN': 20, 'DAD': 15},  # Updated Vietnam hubs
    'AE': {'DXB': 15, 'AUH': 10},

    # Oceania
    'AU': {'SYD': 30, 'MEL': 25, 'BNE': 25, 'PER': 20},
    'NZ': {'AKL': 20},

    # South America
    'BR': {'GRU': 35, 'BSB': 30, 'GIG': 25},
    'AR': {'EZE': 25, 'AEP': 20},
    'CO': {'BOG': 25},
    'CL': {'SCL': 20},
    'PE': {'LIM': 20},

    # Africa
    'ZA': {'JNB': 25, 'CPT': 20},
    'EG': {'CAI': 20},
    'ET': {'ADD': 20},
    'KE': {'NBO': 20},
    'MA': {'CMN': 15}
}


def process_country_airports(args):
    """Process airports for a single country."""
    country_code, country_airports_df, major_hubs = args
    connections = []

    # Create a set to track processed airport pairs to ensure bidirectional connections
    processed_pairs = set()

    # Process each airport in the country
    for idx, origin_airport in country_airports_df.iterrows():
        # Skip if missing coordinates
        if pd.isna(origin_airport['latitude']) or pd.isna(origin_airport['longitude']):
            continue

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

        # Get connection parameters based on airport status
        iata_code = origin_airport['iata_code']
        country_hubs = major_hubs.get(country_code, {})

        # Determine number of connections based on airport importance
        if iata_code in country_hubs:
            # Major hub handling - connect to specified number of airports
            target_connections = country_hubs[iata_code]
            # Select airports prioritizing other hubs and larger airports
            selected_airports = domestic_airports.sort_values(
                ['is_hub', 'airport_type', 'distance'],
                ascending=[False, True, True]
            ).head(target_connections)
        else:
            # Regular airport handling
            if origin_airport['is_hub']:
                target_connections = 25
            elif origin_airport['airport_type'] == 'large_airport':
                target_connections = 15
            else:
                # Medium airports connect to all hubs and large airports in the country
                selected_airports = domestic_airports[
                    (domestic_airports['is_hub']) |
                    (domestic_airports['airport_type'] == 'large_airport')
                ]
                # Add closest medium airports if needed
                if len(selected_airports) < 8:
                    additional_airports = domestic_airports[
                        ~domestic_airports.index.isin(selected_airports.index)
                    ].sort_values('distance').head(8 - len(selected_airports))
                    selected_airports = pd.concat(
                        [selected_airports, additional_airports])

        # For non-medium airports, select based on target connections
        if not (origin_airport['airport_type'] == 'medium_airport' and not origin_airport['is_hub']):
            selected_airports = domestic_airports.sort_values(
                ['is_hub', 'airport_type', 'distance'],
                ascending=[False, True, True]
            ).head(target_connections)

        # Add connections to the list (both directions)
        for _, dest in selected_airports.iterrows():
            # Create a unique identifier for this airport pair (sorted to handle both directions)
            pair_id = tuple(
                sorted([origin_airport['iata_code'], dest['iata_code']]))

            # Only process if we haven't seen this pair before
            if pair_id not in processed_pairs:
                # Add the forward connection
                connections.append({
                    'country': country_code,
                    'origin_airport': origin_airport['iata_code'],
                    'origin_name': origin_airport['name'],
                    'origin_city': origin_airport['city'],
                    'origin_type': origin_airport['airport_type'],
                    'origin_is_hub': origin_airport['is_hub'],
                    'destination_airport': dest['iata_code'],
                    'destination_name': dest['name'],
                    'destination_city': dest['city'],
                    'destination_type': dest['airport_type'],
                    'destination_is_hub': dest['is_hub'],
                    'distance_km': round(dest['distance'], 2)
                })

                # Add the reverse connection
                connections.append({
                    'country': country_code,
                    'origin_airport': dest['iata_code'],
                    'origin_name': dest['name'],
                    'origin_city': dest['city'],
                    'origin_type': dest['airport_type'],
                    'origin_is_hub': dest['is_hub'],
                    'destination_airport': origin_airport['iata_code'],
                    'destination_name': origin_airport['name'],
                    'destination_city': origin_airport['city'],
                    'destination_type': origin_airport['airport_type'],
                    'destination_is_hub': origin_airport['is_hub'],
                    'distance_km': round(dest['distance'], 2)
                })

                # Mark this pair as processed
                processed_pairs.add(pair_id)

    return connections


def create_domestic_connections(airports_df):
    """Create domestic flight connections for each country using parallel processing."""
    # Group airports by country
    country_groups = airports_df.groupby('country_code')

    # Prepare arguments for parallel processing
    process_args = [
        (country_code, group, MAJOR_GLOBAL_HUBS)
        for country_code, group in country_groups
        if len(group) >= 2  # Skip countries with less than 2 airports
    ]

    # Use parallel processing to generate connections
    num_cores = max(1, cpu_count() - 1)  # Leave one core free
    print(f"Using {num_cores} CPU cores for parallel processing...")

    with Pool(num_cores) as pool:
        all_connections = pool.map(process_country_airports, process_args)

    # Flatten the list of connections
    connections = list(itertools.chain.from_iterable(all_connections))

    return pd.DataFrame(connections)


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

    # Print statistics
    print("\nDomestic Connection Statistics:")
    print(f"Total connections: {len(connections_df)}")
    print(f"Countries covered: {len(connections_df['country'].unique())}")

    # Print top 10 countries by number of domestic connections
    print("\nTop 10 countries by number of domestic connections:")
    country_stats = connections_df['country'].value_counts().head(10)
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
        continent_hubs = connections_df[
            (connections_df['country'].isin(countries)) &
            (connections_df['origin_is_hub'] == True)
        ]
        hub_stats = continent_hubs.groupby('origin_airport').agg({
            'destination_airport': 'count',
            'country': 'first'
        }).sort_values('destination_airport', ascending=False).head(5)

        for idx, row in hub_stats.iterrows():
            print(
                f"{idx} ({row['country']}): {row['destination_airport']} connections")

    # Print example connections for Vietnam
    print("\nExample connections in Vietnam:")
    vn_connections = connections_df[connections_df['country'] == 'VN'].sample(
        min(10, len(connections_df)))
    for _, conn in vn_connections.iterrows():
        print(f"{conn['origin_airport']} ({conn['origin_city']}) ↔ "
              f"{conn['destination_airport']} ({conn['destination_city']}): "
              f"{conn['distance_km']}km")


if __name__ == "__main__":
    main()
