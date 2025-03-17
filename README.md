# Process Area Extraction by Multilevel Resource Detection for Object-Centric Process Mining

Process Areas are parts of the process that belong together and should be analyzed together. 
A process area consists of certain object types, activties, and resources.
The object types are those types that belong together and form the basis of the process area.
The activities contain all activities relevant for this area. 
The resources are other object types that act as a resource for those object types that make up this process area.

## Installation
clone this repository and install the required dependecies using `pipenv install`.

## Usage

The process area mining algorithm is available as the `mlpaDiscovery()` function in the ;LPAMiner.py file.
It requires an object centric event log loaded with the ocpa library as input.
Additionally one can specify the tau parameter of the totem miner that defines for which percentace of object pairs a realtion has to hold in order to end up in the mined totem model.
For eample `mlpaDiscovery(logistic_ocel, tau=0.9)` with the publicly accessible logstic event log results in the following process areas:

![Process Areas Image](/example-logistic-process-areas.png)