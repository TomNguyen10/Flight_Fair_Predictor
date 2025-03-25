# World Airports Map Generator

This script creates an interactive map of airports worldwide, showing both large and medium-sized airports that offer scheduled service.

## Features

- Interactive web-based map with worldwide coverage
- Distinguishes between large airports (red) and medium airports (blue)
- Detailed popup information for each airport including:
  - Airport name
  - IATA code
  - Country
  - Airport type
  - Elevation
- Marker clustering for improved performance
- Fullscreen viewing option
- Uses real-time data from OurAirports database

## Requirements

- Python 3.7+
- Required packages listed in `requirements.txt`

## Installation

1. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the script:

```bash
python create_airport_map.py
```

2. Open the generated `world_airports_map.html` file in your web browser to view the interactive map.

## Map Features

- Red markers: Large airports
- Blue markers: Medium airports
- Click on any marker to see detailed airport information
- Zoom and pan functionality
- Marker clustering for better performance with large numbers of airports
- Clean, modern CartoDB base map
- Fullscreen viewing option

## Data Source

The airport data is sourced from OurAirports, a free and open database of airport information.
