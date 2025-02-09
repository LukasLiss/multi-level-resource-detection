from ocpa.objects.log.importer.ocel2.sqlite import factory as ocel_import_factory
from ocpa.algo.discovery.ocpn import algorithm as ocpn_discovery_factory
from ocpa.visualization.oc_petri_net import factory as ocpn_vis_factory

ocel = ocel_import_factory.apply("./example-data/game-data_v06.sqlite")

ocpn = ocpn_discovery_factory.apply(ocel, parameters={"debug": False})
ocpn_vis_factory.save(ocpn_vis_factory.apply(ocpn), "./example-data/oc_petri_net.png")
