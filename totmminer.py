# imports
from datetime import datetime
from ocpa.objects.log.importer.ocel2.sqlite import factory as ocel_import_factory
import json

# load the log
# filename = "./example-data/running-example.sqlite"
# filename = "./example-data/totm-example.sqlite"
foldername = "./uploaded-files/"
DATEFORMAT = "%Y-%m-%d %H:%M:%S"


def turn_keys_in_str(p_dict):
    old_dict_keys = list(p_dict.keys())
    for k in old_dict_keys:
        k_value = p_dict[k]
        del p_dict[k]
        p_dict[str(k)] = k_value


def minetotm(fileid):
    filename = foldername + fileid
    ocel = ocel_import_factory.apply(filename)

    #print(len(ocel.process_executions))

    # temporal relation constants (constants serving as a representation that is easier to understand than just the numbers)
    TR_DEPENDENT = "D"
    TR_DEPENDENT_INVERSE = "Di"
    TR_INITIATING = "I"
    TR_INITIATING_REVERSE = "Ii"
    TR_PARALLEL = "P"
    # temporal relations results
    temporal_relations: dict[tuple[
        str, str], int] = dict()  # the tuple of strings represents the directed relation between two types, the dict counts then how often each relation was found
    h_temporal_relations: dict[tuple[str, str], dict[str, int]] = dict()  # stores all the temporal relations found

    # temporal cardinality constants
    TC_ONE_ONE = "1-1"
    TC_ONE_MANY = "1-M"
    TC_MANY_ONE = "M-1"
    TC_MANY_MANY = "M-M"
    # temporal cardinality results
    temporal_cardinalities: dict[tuple[
        str, str], int] = dict()  # the tuple of strings represents the directed relation between two types, the int is one of the constants above
    h_temporal_cardinalities: dict[tuple[str, str], dict[str, int]] = dict()  # stores all the temporal cardinalities found

    # overall cardinality
    OC_ONE_ONE = "1-1"
    OC_ONE_MANY = "1-M"
    OC_MANY_ONE = "M-1"
    OC_MANY_MANY = "M-M"
    # temporal cardinality results
    overall_cardinalities: dict[tuple[
        str, str], int] = dict()  # the tuple of strings represents the directed relation between two types, the int is one of the constants above
    h_overall_cardinalities: dict[tuple[str, str], dict[str, int]] = dict()  # stores all the overall cardinalities found

    # object min times (omint_L(o))
    o_min_times: dict[
        str, datetime] = dict()  # str identifier of the object maps to the earliest time recorded for that object in the event log
    # object max times (omaxt_L(o))
    o_max_times: dict[
        str, datetime] = dict()  # str identifier of the object maps to the last time recorded for that object in the event log

    # get a list of all object types (or variable that is filled while passing through the process executions)
    type_relations: set[set[str, str]] = set()  # stores all connected types

    # iterate over each process execution (variant not enough because isomorphic process execution graphs do not guarantee same temporal relations
    for px in ocel.process_executions:
        # setup variable to store each object of the process execution
        px_objects = set()
        # setup dictionary to map object type to the objects of this process execution
        px_type_to_obj: dict[str, set[str]] = dict()
        # setup variable to store each ???
        # iterate over each event in that process execution
        for ev in px:
            # get the timestamp and set of objects for that event (store objects in a dictionary that maps object types to objects
            ev_timestamp = datetime.strptime(str(ocel.get_value(ev, 'event_timestamp')), DATEFORMAT)
            ev_type_to_obj = dict()
            for obj_type in ocel.object_types:
                obj_list = ocel.get_value(ev, obj_type)
                if not obj_list:
                    continue
                ev_type_to_obj[obj_type] = obj_list
                # add objects to the process execution level variable that stores the objects
                px_type_to_obj.setdefault(obj_type, set())
                px_type_to_obj[obj_type].update(obj_list)
                # fill o_min_times and o_max_times
                for obj in obj_list:
                    o_min_times.setdefault(obj, ev_timestamp)
                    if ev_timestamp < o_min_times[obj]:  # todo check if comparison of datetimes works correctly here
                        o_min_times[obj] = ev_timestamp
                    o_max_times.setdefault(obj, ev_timestamp)
                    if ev_timestamp > o_max_times[obj]:  # todo check if comparison of datetimes works correctly here
                        o_max_times[obj] = ev_timestamp

            # fill h_temporal_cardinality
            # -> for each combination of object types check weather the set of objects is size 1 or more and add h_temporal cardinality accordingly
            for obj_type1 in ev_type_to_obj.keys():
                t1_is_one = True if len(ev_type_to_obj[
                                            obj_type1]) == 1 else False  # todo this assumes that there is no empty list but that should never exist, but make sure it holds
                for obj_type2 in ev_type_to_obj.keys():
                    t2_is_one = True if len(ev_type_to_obj[obj_type2]) == 1 else False
                    if t1_is_one and t2_is_one:
                        h_temporal_cardinalities.setdefault((obj_type1, obj_type2), dict())
                        h_temporal_cardinalities[(obj_type1, obj_type2)].setdefault(TC_ONE_ONE, 0)
                        h_temporal_cardinalities[(obj_type1, obj_type2)][TC_ONE_ONE] += 1
                    elif t1_is_one and not t2_is_one:
                        h_temporal_cardinalities.setdefault((obj_type1, obj_type2), dict())
                        h_temporal_cardinalities[(obj_type1, obj_type2)].setdefault(TC_ONE_MANY, 0)
                        h_temporal_cardinalities[(obj_type1, obj_type2)][TC_ONE_MANY] += 1
                    elif not t1_is_one and t2_is_one:
                        h_temporal_cardinalities.setdefault((obj_type1, obj_type2), dict())
                        h_temporal_cardinalities[(obj_type1, obj_type2)].setdefault(TC_MANY_ONE, 0)
                        h_temporal_cardinalities[(obj_type1, obj_type2)][TC_MANY_ONE] += 1
                    elif not t1_is_one and not t2_is_one:
                        h_temporal_cardinalities.setdefault((obj_type1, obj_type2), dict())
                        h_temporal_cardinalities[(obj_type1, obj_type2)].setdefault(TC_MANY_MANY, 0)
                        h_temporal_cardinalities[(obj_type1, obj_type2)][TC_MANY_MANY] += 1

        # fill h_overall_cardinality
        # -> for each combination of object types check weather the set of objects is size 1 or more and add h_temporal cardinality accordingly
        for obj_type1 in px_type_to_obj.keys():
            t1_is_one = True if len(px_type_to_obj[
                                        obj_type1]) == 1 else False  # todo this assumes that there is no empty list but that should never exist, but make sure it holds
            for obj_type2 in px_type_to_obj.keys():
                t2_is_one = True if len(px_type_to_obj[obj_type2]) == 1 else False
                if t1_is_one and t2_is_one:
                    h_overall_cardinalities.setdefault((obj_type1, obj_type2), dict())
                    h_overall_cardinalities[(obj_type1, obj_type2)].setdefault(TC_ONE_ONE, 0)
                    h_overall_cardinalities[(obj_type1, obj_type2)][TC_ONE_ONE] += 1
                elif t1_is_one and not t2_is_one:
                    h_overall_cardinalities.setdefault((obj_type1, obj_type2), dict())
                    h_overall_cardinalities[(obj_type1, obj_type2)].setdefault(TC_ONE_MANY, 0)
                    h_overall_cardinalities[(obj_type1, obj_type2)][TC_ONE_MANY] += 1
                elif not t1_is_one and t2_is_one:
                    h_overall_cardinalities.setdefault((obj_type1, obj_type2), dict())
                    h_overall_cardinalities[(obj_type1, obj_type2)].setdefault(TC_MANY_ONE, 0)
                    h_overall_cardinalities[(obj_type1, obj_type2)][TC_MANY_ONE] += 1
                elif not t1_is_one and not t2_is_one:
                    h_overall_cardinalities.setdefault((obj_type1, obj_type2), dict())
                    h_overall_cardinalities[(obj_type1, obj_type2)].setdefault(TC_MANY_MANY, 0)
                    h_overall_cardinalities[(obj_type1, obj_type2)][TC_MANY_MANY] += 1

        # fill h_temporal relations
        # -> for each combination of object types check temporal relations
        for obj_type1 in px_type_to_obj.keys():
            for obj_type2 in px_type_to_obj.keys():
                is_dependent = True
                is_dependent_inverse = True
                is_initiating = True
                is_initiating_inverse = True
                is_parallel = True
                # check each object combination
                for obj_t1 in px_type_to_obj[obj_type1]:
                    for obj_t2 in px_type_to_obj[obj_type2]:
                        # is dependent?
                        # for all objects in t1 check that all objects in t2 start later and end earlier
                        if not (o_min_times[obj_t1] <= o_min_times[obj_t2] <= o_max_times[obj_t2] <= o_max_times[obj_t1]):
                            is_dependent = False
                        # is dependent inverse?
                        if not (o_min_times[obj_t2] <= o_min_times[obj_t1] <= o_max_times[obj_t1] <= o_max_times[obj_t2]):
                            # print(f"Di false because not: {o_min_times[obj_t2]} <= {o_min_times[obj_t1]} <= {o_max_times[obj_t1]} <= {o_max_times[obj_t2]}")
                            is_dependent_inverse = False
                        # is initiating?
                        # for all object in t1 check that start_obj_t1 <= start_obj_t2 <= end_obj_t1 <= end_obj_t2
                        if not (o_min_times[obj_t1] <= o_min_times[obj_t2] <= o_max_times[obj_t1] <= o_max_times[obj_t2]):
                            is_initiating = False
                        # is initiating reverse?
                        if not (o_min_times[obj_t2] <= o_min_times[obj_t1] <= o_max_times[obj_t2] <= o_max_times[obj_t1]):
                            is_initiating_inverse = False
                # store temporal relation
                h_temporal_relations.setdefault((obj_type1, obj_type2), dict())
                if is_dependent:
                    h_temporal_relations[(obj_type1, obj_type2)].setdefault(TR_DEPENDENT, 0)
                    h_temporal_relations[(obj_type1, obj_type2)][TR_DEPENDENT] += 1
                if is_dependent_inverse:
                    h_temporal_relations[(obj_type1, obj_type2)].setdefault(TR_DEPENDENT_INVERSE, 0)
                    h_temporal_relations[(obj_type1, obj_type2)][TR_DEPENDENT_INVERSE] += 1
                elif is_initiating:
                    h_temporal_relations[(obj_type1, obj_type2)].setdefault(TR_INITIATING, 0)
                    h_temporal_relations[(obj_type1, obj_type2)][TR_INITIATING] += 1
                elif is_initiating_inverse:
                    h_temporal_relations[(obj_type1, obj_type2)].setdefault(TR_INITIATING_REVERSE, 0)
                    h_temporal_relations[(obj_type1, obj_type2)][TR_INITIATING_REVERSE] += 1
                else:
                    h_temporal_relations[(obj_type1, obj_type2)].setdefault(TR_PARALLEL, 0)
                    h_temporal_relations[(obj_type1, obj_type2)][TR_PARALLEL] += 1

        # print process exec results
        # print("TR:")
        # print(h_temporal_relations)
        # print("TC:")
        # print(h_temporal_cardinalities)
        # print("OC:")
        # print(h_overall_cardinalities)

    # combine the individual observations per process execution together
    all_object_types = ocel.object_types
    # combine temporal cardinality
    countings_overall_temporal_cardinality = 0
    for relation in h_temporal_cardinalities.keys():
        countings_in_relation = h_temporal_cardinalities[relation].get(TC_ONE_ONE, 0) + h_temporal_cardinalities[
            relation].get(TC_ONE_MANY, 0) + h_temporal_cardinalities[relation].get(TC_MANY_ONE, 0) + \
                                h_temporal_cardinalities[relation].get(TC_MANY_MANY, 0)
        countings_overall_temporal_cardinality += countings_in_relation
        h_temporal_cardinalities[relation][TC_ONE_ONE] = h_temporal_cardinalities[relation].get(TC_ONE_ONE,
                                                                                                0) / countings_in_relation  # todo check that this is not division by 0
        h_temporal_cardinalities[relation][TC_ONE_MANY] = h_temporal_cardinalities[relation].get(TC_ONE_MANY,
                                                                                                 0) / countings_in_relation
        h_temporal_cardinalities[relation][TC_MANY_ONE] = h_temporal_cardinalities[relation].get(TC_MANY_ONE,
                                                                                                 0) / countings_in_relation
        h_temporal_cardinalities[relation][TC_MANY_MANY] = h_temporal_cardinalities[relation].get(TC_MANY_MANY,
                                                                                                  0) / countings_in_relation
        h_temporal_cardinalities[relation] = {"support": countings_in_relation,
                                              "relations": h_temporal_cardinalities[relation]}
    for relation in h_temporal_cardinalities.keys():
        h_temporal_cardinalities[relation]["support"] = h_temporal_cardinalities[relation][
                                                            "support"] / countings_overall_temporal_cardinality
    temporal_cardinalities = h_temporal_cardinalities

    # combine overall cardinality
    countings_overall_cardinality = 0
    for relation in h_overall_cardinalities.keys():
        countings_in_relation = h_overall_cardinalities[relation].get(OC_ONE_ONE, 0) + h_overall_cardinalities[
            relation].get(OC_ONE_MANY, 0) + h_overall_cardinalities[relation].get(OC_MANY_ONE, 0) + h_overall_cardinalities[
                                    relation].get(OC_MANY_MANY, 0)
        countings_overall_cardinality += countings_in_relation
        h_overall_cardinalities[relation][OC_ONE_ONE] = h_overall_cardinalities[relation].get(OC_ONE_ONE,
                                                                                              0) / countings_in_relation  # todo check that this is not division by 0
        h_overall_cardinalities[relation][OC_ONE_MANY] = h_overall_cardinalities[relation].get(OC_ONE_MANY,
                                                                                               0) / countings_in_relation
        h_overall_cardinalities[relation][OC_MANY_ONE] = h_overall_cardinalities[relation].get(OC_MANY_ONE,
                                                                                               0) / countings_in_relation
        h_overall_cardinalities[relation][OC_MANY_MANY] = h_overall_cardinalities[relation].get(OC_MANY_MANY,
                                                                                                0) / countings_in_relation
        h_overall_cardinalities[relation] = {"support": countings_in_relation,
                                             "relations": h_overall_cardinalities[relation]}
    for relation in h_overall_cardinalities.keys():
        h_overall_cardinalities[relation]["support"] = h_overall_cardinalities[relation][
                                                           "support"] / countings_overall_cardinality
    overall_cardinalities = h_overall_cardinalities

    # combine temporal relations
    countings_overall_temproal_relation = 0
    for relation in h_temporal_relations.keys():
        countings_in_relation = h_temporal_relations[relation].get(TR_DEPENDENT, 0) + h_temporal_relations[relation].get(
            TR_DEPENDENT_INVERSE, 0) + h_temporal_relations[relation].get(TR_INITIATING, 0) + h_temporal_relations[
                                    relation].get(TR_INITIATING_REVERSE, 0) + h_temporal_relations[relation].get(
            TR_PARALLEL, 0)
        countings_overall_temproal_relation += countings_in_relation
        h_temporal_relations[relation][TR_DEPENDENT] = h_temporal_relations[relation].get(TR_DEPENDENT,
                                                                                          0) / countings_in_relation  # todo check that this is not division by 0
        h_temporal_relations[relation][TR_DEPENDENT_INVERSE] = h_temporal_relations[relation].get(TR_DEPENDENT_INVERSE,
                                                                                                  0) / countings_in_relation
        h_temporal_relations[relation][TR_INITIATING] = h_temporal_relations[relation].get(TR_INITIATING,
                                                                                           0) / countings_in_relation
        h_temporal_relations[relation][TR_INITIATING_REVERSE] = h_temporal_relations[relation].get(TR_INITIATING_REVERSE,
                                                                                                   0) / countings_in_relation
        h_temporal_relations[relation][TR_PARALLEL] = h_temporal_relations[relation].get(TR_PARALLEL,
                                                                                         0) / countings_in_relation
        h_temporal_relations[relation] = {"support": countings_in_relation,
                                          "relations": h_temporal_relations[relation]}
    for relation in h_temporal_relations.keys():
        h_temporal_relations[relation]["support"] = h_temporal_relations[relation][
                                                        "support"] / countings_overall_temproal_relation
    temporal_relations = h_temporal_relations


    # print("TR:")
    # print(temporal_relations)
    # print("TC:")
    # print(temporal_cardinalities)
    # print("OC:")
    # print(overall_cardinalities)

    # json requires str as key in dictonary therefore replace each key with string representation
    turn_keys_in_str(temporal_relations)
    turn_keys_in_str(temporal_cardinalities)
    turn_keys_in_str(overall_cardinalities)

    # xport to json
    json_export = json.dumps({
        "types": all_object_types,
        "TR": temporal_relations,
        "TC": temporal_cardinalities,
        "OC": overall_cardinalities
    })

    return(json_export)