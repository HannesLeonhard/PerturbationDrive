# This code is used in the paper
# "Model-based exploration of the frontier of behaviours for deep learning system testing"
# by V. Riccio and P. Tonella
# https://doi.org/10.1145/3368089.3409730
import copy
from random import randint
from typing import List, Tuple
from shapely.geometry import Point

from .Roads.simulator_road import SimulatorRoad

import math
import numpy as np

from RoadGenerator.RoadGenerator import RoadGenerator
from RoadGenerator.Roads.road import Road
from RoadGenerator.Roads.road_polygon import RoadPolygon
from RoadGenerator.Roads.bbox import RoadBoundingBox
from RoadGenerator.Roads.catmull_rom import catmull_rom


from shapely.errors import ShapelyDeprecationWarning
import warnings

warnings.simplefilter("ignore", ShapelyDeprecationWarning)


class RandomRoadGenerator(RoadGenerator):
    """Generate random roads given the configuration parameters"""

    NUM_INITIAL_SEGMENTS_THRESHOLD = 2
    NUM_UNDO_ATTEMPTS = 20

    def __init__(
        self,
        map_size: int,
        num_control_nodes=8,
        max_angle=270,
        seg_length=25,
        num_spline_nodes=20,
        initial_node=(125.0, 0.0, -28.0, 4.0),
        bbox_size=(0, 0, 250, 250),
    ):
        assert num_control_nodes > 1 and num_spline_nodes > 0
        assert 0 <= max_angle <= 360
        assert seg_length > 0
        assert len(initial_node) == 4 and len(bbox_size) == 4
        self.map_size = map_size
        self.num_control_nodes = num_control_nodes
        self.num_spline_nodes = num_spline_nodes
        self.initial_node = initial_node
        self.max_angle = max_angle
        self.seg_length = seg_length
        self.road_bbox = RoadBoundingBox(bbox_size=bbox_size)

        self.previous_road: Road = None

        assert not self.road_bbox.intersects_vertices(point=self._get_initial_point())

    def set_max_angle(self, max_angle: int) -> None:
        assert max_angle > 0, "Max angle must be > 0. Found: {}".format(max_angle)
        self.max_angle = max_angle

    def generate_control_nodes(self, attempts=NUM_UNDO_ATTEMPTS) -> List[Tuple[float]]:
        condition = True
        while condition:
            nodes = [self._get_initial_control_node(), self.initial_node]

            # i_valid is the number of valid generated control nodes.
            i_valid = 0

            # When attempt >= attempts and the skeleton of the road is still invalid,
            # the construction of the skeleton starts again from the beginning.
            # attempt is incremented every time the skeleton is invalid.
            attempt = 0

            while i_valid < self.num_control_nodes and attempt <= attempts:
                nodes.append(
                    self._get_next_node(
                        nodes[-2], nodes[-1], self._get_next_max_angle(i_valid)
                    )
                )
                road_polygon = RoadPolygon.from_nodes(nodes)

                # budget is the number of iterations used to attempt to add a valid next control node
                # before also removing the previous control node.
                budget = self.num_control_nodes - i_valid
                assert budget >= 1

                intersect_boundary = self.road_bbox.intersects_boundary(
                    road_polygon.polygons[-1]
                )
                is_valid = road_polygon.is_valid() and (
                    ((i_valid == 0) and intersect_boundary)
                    or ((i_valid > 0) and not intersect_boundary)
                )
                while not is_valid and budget > 0:
                    nodes.pop()
                    budget -= 1
                    attempt += 1

                    nodes.append(
                        self._get_next_node(
                            nodes[-2], nodes[-1], self._get_next_max_angle(i_valid)
                        )
                    )
                    road_polygon = RoadPolygon.from_nodes(nodes)

                    intersect_boundary = self.road_bbox.intersects_boundary(
                        road_polygon.polygons[-1]
                    )
                    is_valid = road_polygon.is_valid() and (
                        ((i_valid == 0) and intersect_boundary)
                        or ((i_valid > 0) and not intersect_boundary)
                    )

                if is_valid:
                    i_valid += 1
                else:
                    assert budget == 0
                    nodes.pop()
                    if len(nodes) > 2:
                        nodes.pop()
                        i_valid -= 1

                assert RoadPolygon.from_nodes(nodes).is_valid()
                assert 0 <= i_valid <= self.num_control_nodes

            # The road generation ends when there are the control nodes plus the two extra nodes needed by
            # the current Catmull-Rom model
            if len(nodes) - 2 == self.num_control_nodes:
                condition = False

        return nodes

    def is_valid(self, control_nodes, sample_nodes):
        return RoadPolygon.from_nodes(
            sample_nodes
        ).is_valid() and self.road_bbox.contains(
            RoadPolygon.from_nodes(control_nodes[1:-1])
        )

    def generate(self, *args, **kwargs) -> str:
        if self.road_to_generate is not None:
            road_to_generate = copy.deepcopy(self.road_to_generate)
            self.road_to_generate = None
            return road_to_generate

        sample_nodes = None
        condition = True
        while condition:
            control_nodes = self.generate_control_nodes()
            control_nodes = control_nodes[1:]
            sample_nodes = catmull_rom(control_nodes, self.num_spline_nodes)
            if self.is_valid(control_nodes, sample_nodes):
                condition = False

        road_points = [Point(node[0], node[1]) for node in sample_nodes]
        control_points = [Point(node[0], node[1], node[2]) for node in control_nodes]

        self.previous_road = SimulatorRoad(
            road_width=4.0,
            road_points=road_points,
            control_points=control_points,
        )

        return self.previous_road.serialize_concrete_representation(
            cr=self.previous_road.get_concrete_representation()
        )

    def _get_initial_point(self) -> Point:
        return Point(self.initial_node[0], self.initial_node[1])

    def _get_initial_control_node(self) -> Tuple[float, float, float, float]:
        x0, y0, z, width = self.initial_node
        x, y = self._get_next_xy(x0, y0, 270)
        assert not (self.road_bbox.bbox.contains(Point(x, y)))

        return x, y, z, width

    def _get_next_node(
        self, first_node, second_node: Tuple[float, float, float, float], max_angle
    ) -> Tuple[float, float, float, float]:
        v = np.subtract(second_node, first_node)
        start_angle = int(np.degrees(np.arctan2(v[1], v[0])))
        angle = randint(start_angle - max_angle, start_angle + max_angle)
        x0, y0, z0, width0 = second_node
        x1, y1 = self._get_next_xy(x0, y0, angle)
        return x1, y1, z0, width0

    def _get_next_xy(self, x0: float, y0: float, angle: float) -> Tuple[float, float]:
        angle_rad = math.radians(angle)
        return x0 + self.seg_length * math.cos(
            angle_rad
        ), y0 + self.seg_length * math.sin(angle_rad)

    def _get_next_max_angle(
        self, i: int, threshold=NUM_INITIAL_SEGMENTS_THRESHOLD
    ) -> float:
        if i < threshold or i == self.num_control_nodes - 1:
            return 0
        else:
            return self.max_angle
