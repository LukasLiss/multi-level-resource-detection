from datetime import datetime
from ocpa.objects.log.importer.ocel2.sqlite import factory as ocel_import_factory
#from ocpa.objects.log.importer.ocel2.xml import factory as ocel_import_factory
from ocpa.objects.log.util import misc as log_util
from ocpa.algo.discovery.ocpn import algorithm as ocpn_discovery_factory
from ocpa.visualization.oc_petri_net import factory as ocpn_vis_factory
import json
from pulp import *
import os
import json

TR_TOTAL = "total"
TR_DEPENDENT = "D"
TR_DEPENDENT_INVERSE = "Di"
TR_INITIATING = "I"
TR_INITIATING_REVERSE = "Ii"
TR_PARALLEL = "P"

# Event cardinality constants
EC_TOTAL = "total"
EC_ZERO = "0"
EC_ONE = "1"
EC_ZERO_ONE = "0...1"
EC_MANY = "1..*"
EC_ZERO_MANY = "0...*"

# Event cardinality constants
LC_TOTAL = "total"
LC_ZERO = "0"
LC_ONE = "1"
LC_ZERO_ONE = "0...1"
LC_MANY = "1..*"
LC_ZERO_MANY = "0...*"

DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Help functions for OCEL2.0

def get_all_event_objects(ocel, event_id):
    obj_ids = []
    for obj_type in ocel.object_types:
        obj_ids += ocel.get_value(event_id, obj_type)
    return obj_ids

def get_most_precise_lc(directed_type_tuple, tau, log_cardinalities):
    total = 0
    if directed_type_tuple in log_cardinalities.keys() and LC_TOTAL in log_cardinalities[directed_type_tuple].keys():
        total = log_cardinalities[directed_type_tuple][LC_TOTAL]

    if total == 0:
        return "ERROR 0"

    if (LC_ZERO in log_cardinalities[directed_type_tuple].keys()) and (
            (log_cardinalities[directed_type_tuple][LC_ZERO] / total) >= tau):
        return LC_ZERO
    if (LC_ONE in log_cardinalities[directed_type_tuple].keys()) and (
            (log_cardinalities[directed_type_tuple][LC_ONE] / total) >= tau):
        return LC_ONE
    if (LC_ZERO_ONE in log_cardinalities[directed_type_tuple].keys()) and (
            (log_cardinalities[directed_type_tuple][LC_ZERO_ONE] / total) >= tau):
        return LC_ZERO_ONE
    if (LC_MANY in log_cardinalities[directed_type_tuple].keys()) and (
            (log_cardinalities[directed_type_tuple][LC_MANY] / total) >= tau):
        return LC_MANY
    if (LC_ZERO_MANY in log_cardinalities[directed_type_tuple].keys()) and (
            (log_cardinalities[directed_type_tuple][LC_ZERO_MANY] / total) >= tau):
        return LC_ZERO_MANY

    return "None"


def get_most_precise_ec(directed_type_tuple, tau, event_cardinalities):
    total = 0
    if directed_type_tuple in event_cardinalities.keys() and EC_TOTAL in event_cardinalities[
        directed_type_tuple].keys():
        total = event_cardinalities[directed_type_tuple][EC_TOTAL]

    if total == 0:
        return "ERROR 0"

    if (EC_ZERO in event_cardinalities[directed_type_tuple].keys()) and (
            (event_cardinalities[directed_type_tuple][EC_ZERO] / total) >= tau):
        return EC_ZERO
    if (EC_ONE in event_cardinalities[directed_type_tuple].keys()) and (
            (event_cardinalities[directed_type_tuple][EC_ONE] / total) >= tau):
        return EC_ONE
    if (EC_ZERO_ONE in event_cardinalities[directed_type_tuple].keys()) and (
            (event_cardinalities[directed_type_tuple][EC_ZERO_ONE] / total) >= tau):
        return EC_ZERO_ONE
    if (EC_MANY in event_cardinalities[directed_type_tuple].keys()) and (
            (event_cardinalities[directed_type_tuple][EC_MANY] / total) >= tau):
        return EC_MANY
    if (EC_ZERO_MANY in event_cardinalities[directed_type_tuple].keys()) and (
            (event_cardinalities[directed_type_tuple][EC_ZERO_MANY] / total) >= tau):
        return EC_ZERO_MANY

    return "None"


def get_most_precise_tr(directed_type_tuple, tau, temporal_relation):
    total = 0
    if directed_type_tuple in temporal_relation.keys() and EC_TOTAL in temporal_relation[directed_type_tuple].keys():
        total = temporal_relation[directed_type_tuple][EC_TOTAL]

    if total == 0:
        return "ERROR 0"

    if (TR_DEPENDENT in temporal_relation[directed_type_tuple].keys()) and (
            (temporal_relation[directed_type_tuple][TR_DEPENDENT] / total) >= tau):
        return TR_DEPENDENT
    if (TR_DEPENDENT_INVERSE in temporal_relation[directed_type_tuple].keys()) and (
            (temporal_relation[directed_type_tuple][TR_DEPENDENT_INVERSE] / total) >= tau):
        return TR_DEPENDENT_INVERSE
    if (TR_INITIATING in temporal_relation[directed_type_tuple].keys()) and (
            (temporal_relation[directed_type_tuple][TR_INITIATING] / total) >= tau):
        return TR_INITIATING
    if (TR_INITIATING_REVERSE in temporal_relation[directed_type_tuple].keys()) and (
            (temporal_relation[directed_type_tuple][TR_INITIATING_REVERSE] / total) >= tau):
        return TR_INITIATING_REVERSE
    if (TR_PARALLEL in temporal_relation[directed_type_tuple].keys()) and (
            (temporal_relation[directed_type_tuple][TR_PARALLEL] / total) >= tau):
        return TR_PARALLEL

    return "None"


def connected_components_undirected(used_nodes, edges):
    graph = {}
    for relation in edges:
        for node in relation:
            if node in used_nodes:  # Only add nodes that are in the types_of_level list
                if node not in graph:
                    graph[node] = set()
                for other in relation:
                    if other != node and other in used_nodes:
                        graph[node].add(other)

    # Step 2: DFS to find connected components
    def dfs(node, visited, component):
        # Adding node to visited set and current component list
        visited.add(node)
        component.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, visited, component)

    # Step 3: Find all connected components
    visited = set()
    connected_components = []

    for node in used_nodes:
        if node not in visited:
            component = []
            dfs(node, visited, component)
            connected_components.append(component)

    return connected_components

def mlpaDiscovery(ocel, tau=0.9):
    time_start_overall = datetime.datetime.now()
    #########################################################################
    #                           Start of totem Part                         #
    #########################################################################
    # object type to event type dict
    obj_typ_to_ev_type: dict[str, set[str]] = dict()
    all_event_types = set()

    # temporal relations results
    h_temporal_relations: dict[tuple[str, str], dict[str, int]] = dict()  # stores all the temporal relations found
    # event cardinality results
    h_event_cardinalities: dict[tuple[str, str], dict[str, int]] = dict()  # stores all the temporal cardinalities found
    # event cardinality results
    h_log_cardinalities: dict[tuple[str, str], dict[str, int]] = dict()  # stores all the temporal cardinalities found

    # object min times (omint_L(o))
    o_min_times: dict[
        str, datetime] = dict()  # str identifier of the object maps to the earliest time recorded for that object in the event log
    # object max times (omaxt_L(o))
    o_max_times: dict[
        str, datetime] = dict()  # str identifier of the object maps to the last time recorded for that object in the event log

    # get a list of all object types (or variable that is filled while passing through the process executions)
    type_relations: set[set[str, str]] = set()  # stores all connected types

    o2o_o2o: dict[str, dict[str, set[
        str]]] = dict()  # dict that describes which objects are connected to which types and for each type which object
    # o2o[obj1][type3] = [obj5, obj6]
    o2o_e2o: dict[str, dict[str, set[str]]] = dict()
    o2o: dict[str, dict[str, set[str]]] = dict()

    # a mapping from type to its objects
    type_to_object = dict()

    for px in ocel.process_executions:
        for ev in px:
            # event infos: objects and timestamps
            ev_timestamp = datetime.strptime(str(ocel.get_value(ev, 'event_timestamp')), DATEFORMAT)

            objects_of_event = get_all_event_objects(ocel, ev)
            for obj in objects_of_event:
                # o2o updating
                o2o.setdefault(obj, dict())
                for type in ocel.object_types:
                    o2o[obj].setdefault(type, set())
                    o2o[obj][type].update(
                        ocel.get_value(ev, type))  # add all objects connected via e2o to each object involved
                # update lifespan information
                o_min_times.setdefault(obj, ev_timestamp)
                if ev_timestamp < o_min_times[obj]:  # todo check if comparison of datetimes works correctly here
                    o_min_times[obj] = ev_timestamp
                o_max_times.setdefault(obj, ev_timestamp)
                if ev_timestamp > o_max_times[obj]:  # todo check if comparison of datetimes works correctly here
                    o_max_times[obj] = ev_timestamp

            # maintain object type to event type dictionary
            eventtype = ocel.get_value(ev, 'event_activity')
            all_event_types.add(eventtype)
            for type in ocel.object_types:
                if len(ocel.get_value(ev, type)) > 0:
                    obj_typ_to_ev_type.setdefault(type, set())
                    obj_typ_to_ev_type[type].add(eventtype)

            # compute event cardinality
            involved_types = []
            obj_count_per_type = dict()
            for type in ocel.object_types:
                obj_list = ocel.get_value(ev, type)
                if not obj_list:
                    continue
                else:
                    type_to_object.setdefault(type, set())
                    type_to_object[type].update(obj_list)
                    involved_types.append(type)
                    obj_count_per_type[type] = len(obj_list)
            # created related types
            for t1 in involved_types:
                for t2 in involved_types:
                    if t1 != t2:
                        type_relations.add(frozenset({t1, t2}))
            # for all type pairs determine
            for type_source in involved_types:
                for type_target in ocel.object_types:
                    # add one to total
                    h_event_cardinalities.setdefault((type_source, type_target), dict())
                    h_event_cardinalities[(type_source, type_target)].setdefault(EC_TOTAL, 0)
                    h_event_cardinalities[(type_source, type_target)][EC_TOTAL] += 1
                    # determine cardinality
                    cardinality = 0
                    if type_target in obj_count_per_type.keys():
                        cardinality = obj_count_per_type[type_target]
                    # add one to matching cardinalities
                    if cardinality == 0:
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ZERO, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ZERO] += 1
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ZERO_ONE, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ZERO_ONE] += 1
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ZERO_MANY, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ZERO_MANY] += 1
                    elif cardinality == 1:
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ONE, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ONE] += 1
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ZERO_ONE, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ZERO_ONE] += 1
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_MANY, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_MANY] += 1
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ZERO_MANY, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ZERO_MANY] += 1
                    elif cardinality > 1:
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_MANY, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_MANY] += 1
                        h_event_cardinalities[(type_source, type_target)].setdefault(EC_ZERO_MANY, 0)
                        h_event_cardinalities[(type_source, type_target)][EC_ZERO_MANY] += 1

    # merge o2o and e2o connected objects
    for (source_o, target_o) in ocel.o2o_graph.graph.edges:
        # print(f"{source_o} - {target_o}")
        type_of_target_o = None
        for type in ocel.object_types:
            if target_o in type_to_object[type]:
                type_of_target_o = type
                break
        if type_of_target_o == None:
            continue
        o2o.setdefault(source_o, dict())
        o2o[source_o].setdefault(type_of_target_o, set())
        o2o[source_o][type_of_target_o].update([source_o])

    # compute log cardinality
    for type_source in ocel.object_types:
        for type_target in ocel.object_types:
            h_temporal_relations.setdefault((type_source, type_target), dict())
            for obj in type_to_object[type_source]:
                h_log_cardinalities.setdefault((type_source, type_target), dict())
                h_log_cardinalities[(type_source, type_target)].setdefault(LC_TOTAL, 0)
                h_log_cardinalities[(type_source, type_target)][LC_TOTAL] += 1

                cardinality = len(o2o[obj][type_target])
                # if type_source == 'products':
                #    print(f"Obj: {obj} Typ: {type_target} Card: {cardinality}")

                if cardinality == 0:
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ZERO, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ZERO] += 1
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ZERO_ONE, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ZERO_ONE] += 1
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ZERO_MANY, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ZERO_MANY] += 1
                elif cardinality == 1:
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ONE, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ONE] += 1
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ZERO_ONE, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ZERO_ONE] += 1
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_MANY, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_MANY] += 1
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ZERO_MANY, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ZERO_MANY] += 1
                elif cardinality > 1:
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_MANY, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_MANY] += 1
                    h_log_cardinalities[(type_source, type_target)].setdefault(LC_ZERO_MANY, 0)
                    h_log_cardinalities[(type_source, type_target)][LC_ZERO_MANY] += 1

                # compute temporal relations
                for obj_target in o2o[obj][type_target]:
                    h_temporal_relations[(type_source, type_target)].setdefault(TR_TOTAL, 0)
                    h_temporal_relations[(type_source, type_target)][TR_TOTAL] += 1
                    if o_min_times[obj_target] <= o_min_times[obj] <= o_max_times[obj] <= o_max_times[obj_target]:
                        h_temporal_relations[(type_source, type_target)].setdefault(TR_DEPENDENT, 0)
                        h_temporal_relations[(type_source, type_target)][TR_DEPENDENT] += 1
                    if o_min_times[obj] <= o_min_times[obj_target] <= o_max_times[obj_target] <= o_max_times[obj]:
                        h_temporal_relations[(type_source, type_target)].setdefault(TR_DEPENDENT_INVERSE, 0)
                        h_temporal_relations[(type_source, type_target)][TR_DEPENDENT_INVERSE] += 1
                    if (o_min_times[obj] <= o_max_times[obj] <= o_min_times[obj_target] <= o_max_times[obj_target]) or (
                            o_min_times[obj] < o_min_times[obj_target] <= o_max_times[obj] < o_max_times[obj_target]):
                        h_temporal_relations[(type_source, type_target)].setdefault(TR_INITIATING, 0)
                        h_temporal_relations[(type_source, type_target)][TR_INITIATING] += 1
                    if (o_min_times[obj_target] <= o_max_times[obj_target] <= o_min_times[obj] <= o_max_times[obj]) or (
                            o_min_times[obj_target] < o_min_times[obj] <= o_max_times[obj_target] < o_max_times[obj]):
                        h_temporal_relations[(type_source, type_target)].setdefault(TR_INITIATING_REVERSE, 0)
                        h_temporal_relations[(type_source, type_target)][TR_INITIATING_REVERSE] += 1
                    # allways parallel
                    h_temporal_relations[(type_source, type_target)].setdefault(TR_PARALLEL, 0)
                    h_temporal_relations[(type_source, type_target)][TR_PARALLEL] += 1

    # setup temporal graph
    tempgraph = {
        'nodes': set(),
        TR_PARALLEL: set(),
        TR_INITIATING: set(),
        TR_DEPENDENT: set(),
    }

    # for each connection give the 6 relations
    for connected_types in type_relations:
        t1, t2 = connected_types
        tempgraph['nodes'].add(t1)
        tempgraph['nodes'].add(t2)
        #print(f"{t1} -> {t2}")

        # get log cardinality
        lc = get_most_precise_lc((t1, t2), tau, h_log_cardinalities)
        lc_i = get_most_precise_lc((t2, t1), tau, h_log_cardinalities)
        #print(f"LC: {lc_i} - {lc}")
        # get event cardinality
        ec = get_most_precise_ec((t1, t2), tau, h_event_cardinalities)
        ec_i = get_most_precise_ec((t2, t1), tau, h_event_cardinalities)
        #print(f"EC: {ec_i} - {ec}")
        # get temporal relation
        tr = get_most_precise_tr((t1, t2), tau, h_temporal_relations)
        tr_i = get_most_precise_tr((t2, t1), tau, h_temporal_relations)
        #print(f"TR: {tr}")
        # add relation to tempgraph
        if tr == TR_DEPENDENT_INVERSE or tr == TR_INITIATING_REVERSE:
            tempgraph[tr_i].add((t2, t1))
        else:
            tempgraph[tr].add((t1, t2))
        # print(f"TRi: {tr_i}")
        #print("")

    tempGraph = tempgraph

    #########################################################################
    #                           End of totem Part                           #
    #########################################################################

    time_totem_done = datetime.datetime.now()

    # transform tempGraph to ILP
    model = LpProblem(name="layer-assignment")

    # Define the decision variables
    level = {i: LpVariable(name=f"level-{i}", lowBound=0, cat='Integer') for i in tempGraph['nodes']}
    z_parallel = {to_string((t1, t2)): LpVariable(name=f"hp-{to_string((t1, t2))}") for (t1, t2) in
                  tempGraph[TR_PARALLEL]}
    z_initiating = {to_string((t1, t2)): LpVariable(name=f"hi-{to_string((t1, t2))}") for (t1, t2) in
                    tempGraph[TR_INITIATING]}

    # constraints
    for (t1, t2) in tempGraph[TR_DEPENDENT]:
        c = level[t2] - level[t1] >= 1
        model += c

    # for parallel we want to minimize the absolute distance. For absolute values one needs an additional constraint
    for (t1, t2) in tempGraph[TR_PARALLEL]:
        c1 = level[t1] - level[t2] - z_parallel[to_string((t1, t2))] <= 0
        c2 = level[t2] - level[t1] - z_parallel[to_string((t1, t2))] <= 0
        model += c1
        model += c2

    # for initiating we want to minimize the absolute distance. For absolute values one needs an additional constraint
    for (t1, t2) in tempGraph[TR_INITIATING]:
        c1 = level[t1] - level[t2] - z_initiating[to_string((t1, t2))] <= 0
        c2 = level[t2] - level[t1] - z_initiating[to_string((t1, t2))] <= 0
        model += c1
        model += c2

    # objective Function
    obj_func = pulp.lpSum(
        [level[t2] - level[t1] for (t1, t2) in tempGraph[TR_DEPENDENT]] + [z_parallel[to_string((t1, t2))] for (t1, t2)
                                                                           in tempGraph[TR_PARALLEL]] + [
            z_initiating[to_string((t1, t2))] for (t1, t2) in tempGraph[TR_INITIATING]])
    model += obj_func

    time_ilp_done = datetime.datetime.now()

    # solve the model
    status = model.solve()

    time_ilp_solve_done = datetime.datetime.now()

    #print
    #for var in level.values():
        #print(f"{var.name}: {var.value()}")

    levels_dict = dict()
    for type in tempGraph['nodes']:
        # print(f"{level[type].name}: {level[type].value()}")
        levels_dict.setdefault(level[type].value(), set())
        levels_dict[level[type].value()].add(type)

    resulting_process_view = {}
    #print("Assignment of object types to layers:")
    #print(levels_dict)
    #print("")
    sorted_levels = [float(k) for k in levels_dict.keys()]
    sorted_levels.sort()  # starting from the lowest level to the highest level
    for l in sorted_levels:
        types_of_level = list(levels_dict[l])
        connected_components_undirected(types_of_level, type_relations)
        resulting_process_view[l] = connected_components_undirected(types_of_level, type_relations)

    #print("Process View (without matching event types):")
    #print(resulting_process_view)
    #print("")

    resulting_process_view_with_events = {}
    # starting from the lowest to the highest level assign the eventtypes to the object groups
    remaining_ev_types = set(list(all_event_types))
    for l in sorted_levels:
        ccs_with_event_types = []
        for cc in resulting_process_view[l]:
            requested_event_types = set()
            for type in cc:
                requested_event_types = requested_event_types.union(obj_typ_to_ev_type[type])
                # print(f"{type} requests: {requested_event_types}")

            assigned_event_types = requested_event_types.intersection(remaining_ev_types)
            # add cc and event types to result
            ccs_with_event_types.append((cc, assigned_event_types))
            # upadate remaining eventtypes
            remaining_ev_types = remaining_ev_types - assigned_event_types

        resulting_process_view_with_events[l] = ccs_with_event_types

    time_mlpa_done = datetime.datetime.now()

    #print("Resulting Process Views with matching Eventtypes:")
    print(resulting_process_view_with_events)

    return (resulting_process_view_with_events,{
        'time_overall': (time_mlpa_done - time_start_overall).total_seconds(),
        'time_totem': (time_totem_done - time_start_overall).total_seconds(),
        'time_ilp': (time_ilp_done - time_totem_done).total_seconds(),
        'time_ilpsolve': (time_ilp_solve_done - time_ilp_done).total_seconds(),
        'time_cc': (time_mlpa_done - time_ilp_solve_done).total_seconds(),
        'O2O': len(type_relations)
    })

#time eval
# folder with event logs
logs_folder = "./time-eval/logs/"
results_folder = "./time-eval/results/"
results_filename = "time-logging.csv"
DATEFORMAT = "%Y-%m-%d %H:%M:%S"

n = 1 # n repetitions

for file in os.listdir(logs_folder):
    if not os.path.isfile(os.path.join(logs_folder, file)):
        continue

    print(f"started file: {file}")

    ocel = ocel_import_factory.apply(os.path.join(logs_folder, file))

    number_px = len(ocel.process_executions)

    print(f"import done for file: {file}")

    (result, time_result) = mlpaDiscovery()

    number_objects = 0
    number_events = 0

    for px in ocel.process_executions:
        number_events += len(px)

    for px_obj in ocel.process_execution_objects:
        number_objects += len(px_obj)

    # todo save pa
    save_result_filename = f"{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json"

    with open(os.path.join(results_folder, save_result_filename), 'w') as json_file:
        json.dump(result, json_file, indent=4)

    with open(results_folder + results_filename, 'a') as resultfile:
        resultfile.write(f"{file};{save_result_filename};{number_objects};{number_events};{number_px};{time_result['O2O']};{time_result['time_overall']},{time_result['time_totem']};{time_result['time_ilp']};{time_result['time_ilpsolve']};{time_result['time_cc']}" + '\n')
