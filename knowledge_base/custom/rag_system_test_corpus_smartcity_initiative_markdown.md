# Aurora Smart City Initiative - Internal Knowledge Base

## Overview

The Aurora Smart City Initiative (ASCI) is a fictional long-term urban development program launched in 2021 by the city of Aurora Heights. The initiative combines transportation, energy, public safety, healthcare, waste management, and citizen services into a unified digital platform.

The city has a population of 2.4 million residents and covers approximately 540 square kilometers. The primary objective of ASCI is to reduce traffic congestion, improve emergency response times, lower carbon emissions, and make public services more accessible.

The project is divided into four phases:

1. Phase 1 (2021-2022): Digital infrastructure setup
2. Phase 2 (2023-2024): Transportation and energy integration
3. Phase 3 (2025-2026): Public safety and healthcare integration
4. Phase 4 (2027-2028): Predictive governance and AI-assisted planning

---

# Transportation System

## Smart Traffic Network

Aurora Heights installed 18,400 IoT traffic sensors across the city. These sensors monitor:

- Vehicle count
- Vehicle speed
- Traffic density
- Average waiting time at intersections
- Pedestrian movement

The sensors transmit data every 12 seconds to the Central Mobility Server (CMS).

The CMS is hosted in two redundant data centers:

- North Ridge Data Center
- South Valley Data Center

If the North Ridge Data Center fails, all traffic control operations automatically switch to the South Valley Data Center within 45 seconds.

## Adaptive Traffic Lights

The city uses adaptive traffic lights manufactured by LumaTraffic Systems.

Important configuration:

| Parameter                        | Value               |
| -------------------------------- | ------------------- |
| Minimum green light duration     | 15 seconds          |
| Maximum green light duration     | 90 seconds          |
| Yellow light duration            | 4 seconds           |
| Pedestrian crossing buffer       | 8 seconds           |
| Emergency override response time | Less than 3 seconds |

The busiest intersection in Aurora Heights is the Grand Avenue - River Street junction, which handles approximately 72,000 vehicles per day.

## Electric Bus Fleet

Aurora Heights operates an electric bus fleet called MetroGreen.

Key details:

- Total buses: 860
- Fully electric buses: 610
- Hybrid buses: 250
- Average battery capacity per electric bus: 420 kWh
- Maximum range per charge: 310 km
- Average daily distance traveled: 198 km

The fleet is maintained at three depots:

1. East Terminal Depot
2. Harbor Line Depot
3. West Industrial Depot

The East Terminal Depot is the largest and can service up to 220 buses simultaneously.

---

# Energy Management

## Renewable Energy Sources

Aurora Heights gets electricity from four primary sources:

| Energy Source       | Contribution |
| ------------------- | ------------ |
| Solar Farms         | 34%          |
| Wind Turbines       | 27%          |
| Hydroelectric Plant | 18%          |
| Natural Gas Backup  | 21%          |

The city's largest solar installation is the Suncrest Solar Field located 18 km east of downtown. It has:

- 412,000 solar panels
- Total generation capacity: 280 MW
- Average daily generation: 1.1 GWh

The wind farm, known as Silver Ridge Wind Park, contains 84 turbines. Each turbine has a rated capacity of 3.6 MW.

## Smart Grid

The smart grid project uses smart meters installed in 91% of households.

Smart meters send electricity usage data every 30 minutes.

Each smart meter records:

- Total energy consumption
- Peak-hour consumption
- Off-peak consumption
- Voltage fluctuations
- Temporary outages

The central utility platform stores data for exactly 5 years before automatic archival.

## Battery Storage Facilities

Aurora Heights maintains three grid-scale battery storage facilities:

| Facility Name          | Capacity | Location          |
| ---------------------- | -------- | ----------------- |
| North Lake Storage     | 180 MWh  | Northern District |
| Pine Valley Storage    | 120 MWh  | Western Hills     |
| Harbor Reserve Storage | 95 MWh   | Harbor Zone       |

The North Lake Storage facility can power approximately 42,000 homes for 3 hours during an emergency.

---

# Public Safety

## Emergency Response Network

The city uses an emergency response platform named SentinelNet.

SentinelNet integrates:

- Police dispatch
- Fire department dispatch
- Ambulance dispatch
- Disaster management alerts

Emergency calls are categorized into five priority levels:

| Priority | Description                          | Target Response Time |
| -------- | ------------------------------------ | -------------------- |
| P1       | Immediate life-threatening emergency | Under 4 minutes      |
| P2       | Serious but stable emergency         | Under 8 minutes      |
| P3       | Urgent non-life-threatening issue    | Under 15 minutes     |
| P4       | Minor issue                          | Under 30 minutes     |
| P5       | Administrative request               | Under 2 hours        |

The average emergency response time in 2025 was 5.8 minutes.

## Surveillance Cameras

Aurora Heights deployed 12,600 smart surveillance cameras.

Camera capabilities include:

- Automatic number plate recognition
- Crowd density estimation
- Smoke and fire detection
- Suspicious object detection
- Facial matching for missing person alerts

Video retention policy:

- Standard footage retention: 30 days
- Criminal investigation footage retention: 3 years
- Footage linked to active court cases: 7 years

## Disaster Preparedness

The city has four designated emergency shelters:

1. Northview Sports Arena
2. Riverbend Convention Center
3. Central Technical University Campus
4. South Harbor Exhibition Hall

The Riverbend Convention Center is the largest shelter and can accommodate 18,000 people.

---

# Healthcare Integration

## Digital Health Platform

Aurora Heights operates a healthcare platform called MedLink.

MedLink connects:

- 14 hospitals
- 62 clinics
- 118 pharmacies
- 46 diagnostic laboratories

Patient records are stored using a unique Health Identity Number (HIN).

A valid HIN follows this pattern:

`AH-YYYY-NNNNNN`

Example:

`AH-2026-483921`

Where:

- AH = Aurora Heights
- YYYY = year of registration
- NNNNNN = six-digit identifier

## Major Hospitals

| Hospital Name                 | Beds | Specialty       |
| ----------------------------- | ---- | --------------- |
| Central Aurora Medical Center | 950  | Multi-specialty |
| North Valley Heart Institute  | 420  | Cardiology      |
| Starlight Children's Hospital | 310  | Pediatrics      |
| Westside Neuro Center         | 280  | Neurology       |

Central Aurora Medical Center handled 148,000 emergency visits in 2025.

## Ambulance Fleet

The ambulance system includes:

- 82 advanced life support ambulances
- 44 basic ambulances
- 12 helicopter emergency units

The helicopter units are stationed at:

- Central Aurora Medical Center
- North Valley Heart Institute
- South Harbor Airport

---

# Waste Management

## Smart Waste Bins

Aurora Heights installed 9,200 smart waste bins.

Each smart bin contains:

- Fill-level sensor
- Temperature sensor
- GPS module
- Internal compactor

The fill-level threshold for automatic collection scheduling is 82%.

If a bin exceeds 95% capacity, it is marked as urgent priority.

## Recycling Statistics

In 2025, Aurora Heights processed:

| Waste Type    | Amount       |
| ------------- | ------------ |
| Plastic       | 182,000 tons |
| Paper         | 141,000 tons |
| Metal         | 74,000 tons  |
| Organic Waste | 266,000 tons |

The city's overall recycling rate reached 68% in 2025.

---

# Citizen Services

## CityConnect Mobile Application

Aurora Heights provides a citizen mobile application called CityConnect.

Features include:

- Bill payments
- Bus tracking
- Complaint registration
- Emergency alerts
- Healthcare appointment booking
- Parking reservation

The application is available on:

- Android
- iOS
- Web browser

In January 2026, the application had 1.46 million active users.

## Complaint Categories

Complaints submitted through CityConnect are divided into categories:

| Category Code | Description          |
| ------------- | -------------------- |
| C101          | Road damage          |
| C102          | Water leakage        |
| C103          | Illegal parking      |
| C104          | Street light failure |
| C105          | Noise complaint      |
| C106          | Garbage overflow     |

Average resolution times:

| Complaint Code | Average Resolution Time |
| -------------- | ----------------------- |
| C101           | 4.5 days                |
| C102           | 2.1 days                |
| C103           | 18 hours                |
| C104           | 1.8 days                |
| C105           | 12 hours                |
| C106           | 8 hours                 |

---

# Internal Security Policies

## Password Policy

Employees working on the ASCI platform must follow these password rules:

- Minimum length: 14 characters
- Must contain uppercase letters
- Must contain lowercase letters
- Must contain at least one number
- Must contain at least one special character
- Password expiration period: 90 days
- Last 8 passwords cannot be reused

## Access Levels

| Access Level | Description                    |
| ------------ | ------------------------------ |
| Level 1      | Read-only access               |
| Level 2      | Data entry and updates         |
| Level 3      | Department administrator       |
| Level 4      | Cross-department administrator |
| Level 5      | Super administrator            |

Only Level 5 administrators can modify disaster response configurations.


