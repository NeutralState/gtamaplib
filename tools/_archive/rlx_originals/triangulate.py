import json
import os
import sys

import numpy as np

from gtamaplib import gtamaplib as ml
from gtamaplib import gtamapdata as md
from gtamaplib import gtamaputils as mu


if sys.argv[1] == "-fs":

    ml.find_four_seasons()
    print("### UPDATE FOUR SEASONS ARGS AND LANDMARKS ###")
    print("### UPDATE TENNIS STADIUM AND METRO CAMERAS ###")


if sys.argv[1] == "-ts":

    area = (-1500, -3000, 500, -1000)
    m = ml.get_map("yanis")
    m.project_camera_parallel("Tennis Stadium (4K)", area=area)
    m.save("triangulate/ts projection.png", area)


if sys.argv[1] == "-mb":

    mu.find_mary_brickell()
    print("### UPDATE MARY BRICKELL LANDMARKS ###")


if sys.argv[1] == "-portofino":

    cam_name_0 = "Port"
    cam_name_1 = "Sidewalk (Jason) (E)"

    cam = ml.get_camera(cam_name_1)
    cam.test_lines()
    lm_name = "Portofino Tower (NW)"
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')
    print("### UPDATE PORTOFINO TOWER (NW) LANDMARK ###")


if sys.argv[1] == "-onk":
    
    cam_name = "Ocean near Keys (N)"
    lm_name = "Four Seasons Hotel Miami (BW)"
    cam = ml.get_camera(cam_name).calibrate_yaw_and_pitch(lm_name)
    cam.render_all().save("triangulate/onk.png")
    print(cam)
    print("### UPDATE OCEAN NEAR KEYS CAMERA ###")


if sys.argv[1] == "-lka":

    """
    ml.find_camera(
        "Leonida Keys 01 (Airplane) (X)",
        [
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (BW)",
            "Portofino Tower (NW)",
            "House with Boat (X)",
        ],
        [
            ("Tennis Stadium (4K)", "Park Grove Condominium (S)"),
            ("Tennis Stadium (4K)", "Homestead Water Tower"),
            ("Tennis Stadium (4K)", "Prison Tower (2)"),
            ("Tennis Stadium (4K)", "Prison Tower (3)"),
            ("Tennis Stadium (4K)", "Prison Tower (4)"),
            ("Tennis Stadium (4K)", "Prison Tower (5)"),
            ("Tennis Stadium (4K)", "Prison Tower (6)"),
            ("Ocean near Keys (N)", "Seven Mile Bridge (3T)"),
            ("Ocean near Keys (N)", "Seven Mile Bridge (6T)"),
            ("Ocean near Keys (N)", "Blue Billboard (Key Lento)"),
            ("Ocean near Keys (N)", "99353 Overseas Hwy"),
            ("Ocean near Keys (N)", "102180 Overseas Hwy"),
            ("House with Boat (X)", "House D (SW)"),
        ],
        ((-4370, -7580), (-4370, -7580)), 25, 1.0,
        # (-11.0, -7.9, 0.1), (55, 71, 0.1),
        (-10.0, -8.9, 0.1), (59, 67, 0.1),
        "dupzor", 1, (-5000, -8000, -3000, -6000),
        None,
        "triangulate/lka"
    )
    print("### UPDATE LEONIDA KEYS AIRPLANE CAMERA ###")
    """

    cam_name = "Leonida Keys 01 (Airplane) (X)"
    cam = ml.get_camera(cam_name)
    lm_names = [f"Seven Mile Bridge ({i}B)" for i in range(1, 22)]
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')


if sys.argv[1] == "-hwt":

    for cam_name_0, cam_name_1, lm_name in (
        ("Ocean near Keys (N)", "Leonida Keys 01 (Airplane) (X)", "Blue Billboard (Key Lento)"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Homestead Water Tower"),
        ("Ocean near Keys (N)", "Leonida Keys 01 (Airplane) (X)", "99353 Overseas Hwy"),
        ("Ocean near Keys (N)", "Leonida Keys 01 (Airplane) (X)", "102180 Overseas Hwy"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Park Grove Condominium (S)"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Prison Tower (2)"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Prison Tower (3)"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Prison Tower (4)"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Prison Tower (5)"),
        ("Tennis Stadium (4K)", "Leonida Keys 01 (Airplane) (X)", "Prison Tower (6)"),
        ("Police Chase (D)", "Leonida Keys 01 (Airplane) (X)", "Red Billboard (Hamlet)"),
        ("Ocean near Keys (N)", "Leonida Keys 01 (Airplane) (X)", "Seven Mile Bridge (3T)"),
        ("Ocean near Keys (N)", "Leonida Keys 01 (Airplane) (X)", "Seven Mile Bridge (6T)"),
        ("Police Chase (A)", "Leonida Keys 01 (Airplane) (X)", "White Billboard (Hamlet)"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')

    cam_name = "Leonida Keys 01 (Airplane) (X)"
    lm_names = (
        "Blimp Bay",
        "Island A (W)", "Island J (E)", "Island N (E)", "Island N (W)",
        "Island S (E)", "Island U (S)", "Island V (S)",
        "Key Lento (A)", "Key Lento (J)",
        "Pin C01R (B)", "Seven Mile Bridge (20B)", "Seven Mile Bridge (5B)",
    )
    cam = ml.get_camera(cam_name)
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')


if sys.argv[1] == "-lkp":

    """
    cam = ml.find_camera(
        "Leonida Keys Postcard (X)",
        [
            "Key Lento (A)",
            "Key Lento (J)",
            "Island A (W)",
            "House with Boat (X)",
            "Portofino Tower (NW)",
        ],
        [
            ("Leonida Keys 01 (Airplane) (X)", "102180 Overseas Hwy"),
            ("Leonida Keys 01 (Airplane) (X)", "Tree on Island J"),
            ("Leonida Keys 01 (Airplane) (X)", "Turkey Point Nuclear Power Station (1)"),
            ("Leonida Keys 01 (Airplane) (X)", "Turkey Point Nuclear Power Station (3)"),
            ("Leonida Keys 01 (Airplane) (X)", "Pin A02R"),
            ("Leonida Keys 01 (Airplane) (X)", "Pin B04R"),
            ("Leonida Keys 01 (Airplane) (X)", "Pin C01R"),
            ("Leonida Keys 01 (Airplane) (X)", "Pin D01R"),
            ("House with Boat (X)", "House D (SW)"),
        ],
        ((-3810, -6800), (-3810, -6800)), 25, 1,
        None, (-13.0, -9.9, 0.1), (40, 55.1, 0.1),
        "martipk", 1, (-5000, -8000, -2000, -5000),
        None, #(-5000, -8000, 4000, 1000),
        "triangulate/lkp"
    )
    print("### UPDATE LEONIDA KEYS POSTCARD CAMERA ###")
    """

    cam_name = "Leonida Keys Postcard (X)"
    cam = ml.get_camera(cam_name)
    lm_names = [f"Keys Bridge ({i}B)" for i in range(1, 8)]
    lm_names += [f"Lake Surprise Viaduct ({i}B)" for i in range(2, 16)]
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')


if sys.argv[1] == "-pins":

    for cam_name_0, cam_name_1, lm_name in (
        ("Leonida Keys 01 (Airplane) (X)", "Leonida Keys Postcard (X)", "102180 Overseas Hwy"),
        ("Leonida Keys 01 (Airplane) (X)", "Leonida Keys Postcard (X)", "Tree on Island J"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')

    cam_name_0 = "Leonida Keys 01 (Airplane) (X)"
    cam_name_1 = "Leonida Keys Postcard (X)"
    pin_names = []
    for lm_name, xy in md.pixels[cam_name_0].items():
        if lm_name.startswith("Pin ") and lm_name in md.pixels[cam_name_1]:
            pin_names.append(lm_name)
    for cam_name_0, cam_name_1, lm_name in [
        ("Leonida Keys 01 (Airplane) (X)", "Leonida Keys Postcard (X)", pin_name)
        for pin_name in pin_names
    ]:
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')

    # get points at ground level
    cam_name = "Leonida Keys Postcard (X)"
    lm_names = (
        "Key Lento (A)", "Key Lento (E)", "Key Lento (J)",
        "Key Lento (U)", "Key Lento (V)", "Key Lento (W)",
        "Island F (E)", "Island F (W)", "Island G (E)", "Island G (W)", "Island J (W)",
        "Island X (S)", "Island Y (S)", "Island Z (S)"
    )
    cam = ml.get_camera(cam_name)
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_directions[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')


if sys.argv[1] == "-lkalkp":

    lka = "Leonida Keys 01 (Airplane) (X)"
    lkp = "Leonida Keys Postcard (X)"
    map_name = "martipk"

    area = (-5000, -8000, 4000, 1000)
    m = ml.get_map(map_name)
    m.project_camera_parallel((lka, lkp), area=area)
    m.save(f"triangulate/lkalkp map.png", area)

    for cam_name in (lka, lkp):
        cam = ml.get_camera(cam_name).open(scale=1)
        cam.render_distance_circles().project_map(map_name).render_camera_info()
        cam.save(f"triangulate/lkalkp {cam_name} {map_name}.png")    

    cam = ml.get_camera(lkp).open(scale=1)
    cam.render_distance_circles().project_camera(lka).render_camera_info()
    cam.save(f"triangulate/lkalkp cameras.png")


if sys.argv[1] == "-kl":

    cam = ml.find_camera(
        "Key Lento",
        [
            "99353 Overseas Hwy",
            "102180 Overseas Hwy",
            "Island G (E)",
            "Island V (S)",
        ],
        [
            ("Leonida Keys Postcard (X)", "Marina Club at Blackwater Sound (N)"),
            ("Leonida Keys Postcard (X)", "Marina Club at Blackwater Sound (S)"),
            ("Leonida Keys Postcard (X)", "500 Pompano Dr"),
            ("Leonida Keys Postcard (X)", "200 Pompano Dr"),
        ],
        ((-1800, -5250), (-1800, -5250)), 25, 1,
        None, (-9.0, -5.9, 0.1), (55, 76, 0.1),
        "martipk", 1, (-4000, -7000, -1000, -4000),
        None, #(-5000, -8000, 4000, 1000),
        "triangulate/kl"
    )
    print("### UPDATE LEONIDA KEYS POSTCARD CAMERA ###")


if sys.argv[1] == "-marina":

    for cam_name_0, cam_name_1, lm_name in (
        ("Leonida Keys Postcard (X)", "Key Lento", "Marina Club at Blackwater Sound (N)"),
        ("Leonida Keys Postcard (X)", "Key Lento", "Marina Club at Blackwater Sound (S)"),
        ("Leonida Keys Postcard (X)", "Key Lento", "500 Pompano Dr"),
        ("Leonida Keys Postcard (X)", "Key Lento", "200 Pompano Dr"),
        ("Leonida Keys Postcard (X)", "Key Lento", "180 Pompano Dr"),
        ("Leonida Keys Postcard (X)", "Key Lento", "Billboard #2 (Key Lento)"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')


if sys.argv[1] == "-k":

    """
    cam = ml.find_camera(
        "Keys",
        [
            "Seven Mile Bridge (20B)",
            "Seven Mile Bridge (5B)",
            "Island V (S)",
            "Blimp Bay",
        ],
        [
            ("Ocean near Keys (E)", "Sombrero Key Light (B)"),
            ("Leonida Keys 01 (Airplane) (X)", "Unnamed Building #1 (Blimp Key)"),
        ],
        ((-6150, -7100), (-6050, -7100)), 25, 1,
        (-22.0, -16.9, 0.1), (55, 71, 0.1),
        "dupzor", 1, (-7000, -8000, -2000, -5000),
        None, #(-7000, -8000, -2000, -5000),
        "triangulate/k"
    )
    print("### UPDATE KEYS CAMERA ###")
    """
    cam_name = "Keys"
    cam = ml.get_camera(cam_name)
    lm_names = [f"New Bahia Honda Bridge ({i}B)" for i in range(1, 40) if i not in (24, 25, 26)]
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')
    lm_names = [f"Old Bahia Honda Bridge ({i}B)" for i in (1, 21)]
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')


if sys.argv[1] == "-bk":

    for cam_name_0, cam_name_1, lm_name in (
        ("Keys", "Leonida Keys 01 (Airplane) (X)", "Unnamed Building #1 (Blimp Key)"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')

    cam_name = "Keys"
    lm_names = (
        "Island W (N)",
    )
    cam = ml.get_camera(cam_name)
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_name}')


if sys.argv[1] == "-klkalkp":

    k = "Keys"
    lka = "Leonida Keys 01 (Airplane) (X)"
    lkp = "Leonida Keys Postcard (X)"
    map_name = "yanis"
    area = (-7000, -8000, 3000, 1000)
    m = ml.get_map(map_name).open(add_padding=True)
    m.project_camera_parallel((k, lka, lkp), area=area)
    m.save(f"triangulate/klkalkp map.png", area)


if sys.argv[1] == "-lkb":
    cam, loss = ml.find_camera(
        "Leonida Keys 05 (Boats)",
        [
            "Blue Billboard (Key Lento)",
            "Pin B01L",
            "Pin C01R",
            "Pin B02R",
            "Pin B02L",
        ],
        [
            ("Leonida Keys Postcard (X)", "House with Pier (E)"),
        ],
        ((-3170.000, -6350.000), (-3170.000, -6350.000)), 25, 1,
        (0, 7.5), (-17.5, -10.0, 0.1), (64.0, 75.0, 0.1),
        "yanis", 1, (-4000, -7000, -2500, -5500),
        None, 
        "triangulate/lkb"
    )


if sys.argv[1] == "-wb":

    # FIXME: can we use continuum?
    fs = ml.FourSeasons()
    fake_cam_name = "Four Seasons Fake Cam"
    md.cameras[fake_cam_name] = {
        "id": "[X]",
        "player": None,
        "xyz": fs.hb58nw,
        "ypr": (0, -89.999, 0),
        "fov": (90, None),
        "size": (3840, 2160)
    }
    md.pixels[fake_cam_name] = {
        "Four Seasons Hotel Miami (W)": (1920, 1080)
    }

    cam = ml.find_camera(
        "Grassrivers 02 (Watson Bay)",
        [
            "Homestead Water Tower",
            "Park Grove Condominium (S)",
            "Prison Tower (2)",
            "Prison Tower (3)",
            "Prison Tower (4)",
            "Prison Tower (5)",
            "Prison Tower (6)",
        ],
        [
            ("Leonida Keys 01 (Airplane) (X)", "Turkey Point Nuclear Power Station (N)"),
            ("Leonida Keys 01 (Airplane) (X)", "Turkey Point Nuclear Power Station (3)"),
            ("Four Seasons Fake Cam", "Four Seasons Hotel Miami (W)")
        ],
        ((-5230, -3360), (-5230, -3360)), 25, 1,
        (-6.5, -5.4, 0.1), (40, 61, 0.1),
        "dupzor", 1, (-6000, -4500, -4000, -2500),
        None,
        "triangulate/wb"
    )
    print("### UPDATE GRASSRIVERS WATSON BAY CAMERA ###")


if sys.argv[1] == "-tp":

    for cam_name_0, cam_name_1, lm_name in (
        ("Airport (X)", "Grassrivers 02 (Watson Bay)", "Latitude on the River (S) (NW)"),
        ("Airport (X)", "Grassrivers 02 (Watson Bay)", "Latitude on the River (S) (SW)"),
        ("Metro (SE) (A) (4K)", "Grassrivers 02 (Watson Bay)", "Nine at Mary Brickell Village (A)"),
        ("Metro (SE) (A) (4K)", "Grassrivers 02 (Watson Bay)", "Nine at Mary Brickell Village (B)"),
        ("Tennis Stadium (4K)", "Grassrivers 02 (Watson Bay)", "Nine at Mary Brickell Village (E)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Park Grove Condominium (C)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Park Grove Condominium (N)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Prison Tower (1)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Turkey Point Nuclear Power Station (N)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Turkey Point Nuclear Power Station (S)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Turkey Point Nuclear Power Station (1)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Turkey Point Nuclear Power Station (2)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "Turkey Point Nuclear Power Station (3)"),
        ("Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)", "WDNA FM SW 248th St"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        if lm_name == "WDNA FM SW 248th St":
            x, y, z = a
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')
    # cam_name_0, cam_name_1 = "Leonida Keys 01 (Airplane) (X)", "Grassrivers 02 (Watson Bay)"
    # lm_name = "WDNA FM SW 248th St"
    # (x, y, z), (z0, z1) = ml.find_landmark_2d(cam_name_0, cam_name_1, lm_name)
    # print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z0:.3f}), # 2D via {cam_name_0} & {cam_name_1}')


if sys.argv[1] == "-p":

    cam = ml.find_camera(
        "Prison",
        [
            "Four Seasons Hotel Miami (NW)",
            "Four Seasons Hotel Miami (SE)",
            "Turkey Point Nuclear Power Station (N)",
            "Turkey Point Nuclear Power Station (3)",
            #"WDNA FM SW 248th St",
            #"Prison Tower (1)",
            #"Prison Tower (2)",
            #"Prison Tower (3)",
            #"Prison Tower (4)",
            #"Prison Tower (5)",
            #"Prison Tower (6)",
        ],
        [
            ("Grassrivers 02 (Watson Bay)", "Prison Tower (1)"),
            ("Grassrivers 02 (Watson Bay)", "Prison Tower (2)"),
            ("Grassrivers 02 (Watson Bay)", "Prison Tower (3)"),
            ("Grassrivers 02 (Watson Bay)", "Prison Tower (4)"),
            ("Grassrivers 02 (Watson Bay)", "Prison Tower (5)"),
            ("Grassrivers 02 (Watson Bay)", "Prison Tower (6)"),
            ("Leonida Keys 01 (Airplane) (X)", "WDNA FM SW 248th St"),
        ],
        ((-3360, -2760), (-3360, -2760)), 25, 1,
        (-4.0, -0.9, 0.1), (70, 90.05, 0.1),
        "dupzor", 1, (-4000, -4000, -2000, -2000),
        (-3500, -3500, -1500, -1500),
        "triangulate/p",
    )
    print("### UPDATE PRISON CAMERA ###")


if sys.argv[1] == "-pt":

    for cam_name_0, cam_name_1, lm_name in (
        ("Leonida Keys 01 (Airplane) (X)", "Prison", "Keys Bridge (C)"),
        ("Vice Beach (B)", "Prison", "Opera Tower"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Miami Tower"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Prison Tower (1)"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Prison Tower (2)"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Prison Tower (3)"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Prison Tower (4)"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Prison Tower (5)"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Prison Tower (6)"),
        ("Vice Beach (B)", "Prison", "Southeast Financial Center"),
        ("Grassrivers 02 (Watson Bay)", "Prison", "Wells Fargo Center"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')
    print("### UPDATE ###")


if sys.argv[1] == "-wc":

    cam_name_0 = "Welcome Center (E)"
    cam_name_1 = "Welcome Center (W)"
    cams = [ml.get_camera(cam_name) for cam_name in (cam_name_0, cam_name_1)]
    for cam in cams:
        cam.test_lines()
        cam.test_player()

    lm_name = "Art Deco Welcome Center (S)"
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')
    print("### UPDATE ###")


if sys.argv[1] == "-park":

    cam_name = "Park"
    lm_name = "Art Deco Welcome Center (S)"
    cam = ml.get_camera(cam_name)
    cam.test_lines()
    cam.test_player()
    cam.calibrate_yaw_and_pitch(lm_name)
    print(cam)
    print("### UPDATE ###")


if sys.argv[1] == "-vb":

    mu.find_vice_beach(
        hfov_range=(62.120, 62.125, 0.01),
        dirname="triangulate/vb"
    )


if sys.argv[1] == "-vba":

    cam = ml.find_camera(
        "Vice Beach (A)",
        [
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (BW)",
            "Four Seasons Hotel Miami (NW)",
            "Four Seasons Hotel Miami (SE)",
        ],
        [
            ("Alley (W)", "Flamingo South Beach (TE)"),
            ("Alley (W)", "Flamingo South Beach (TNE)"),
            ("Alley (W)", "Flamingo South Beach (TSE)"),
            ("Sidewalk (Jason) (E)", "The Floridian"),
            ("Park", "Hotel Breakwater"),
            ("Park", "Jenny Hostel (NE)"),
            ("Port", "Murano Grande"),
            ("Park", "1500 Ocean Dr"),
            ("Tennis Court (SE)", "Old City Hall"),
            ("Tennis Court (SE)", "1000 Venetian Way (SW)"),
        ],
        ((2350, 1100), (2350, 1100)), 25, 1,
        (40, 60), (-14, -10.9, 0.1), (61, 64.1, 0.1),
        "yanis", 1, (1000, 0, 3000, 2000),
        (500, -500, 2500, 1500),
        "triangulate/vba"
    )

    cam.register()
    lm_names = ("Beach (G)", "Beach (H)")
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')


if sys.argv[1] == "-vbb":

    cam = ml.find_camera(
        "Vice Beach (B)",
        [
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (BW)",
            "Four Seasons Hotel Miami (NW)",
            "Four Seasons Hotel Miami (SE)",
            # "Wells Fargo Center",
        ],
        [
            #("Prison", "Southeast Financial Center"),
            #("Prison", "Wells Fargo Center"),
            #("Prison", "Opera Tower"),
            #("Leonida Keys 01 (Airplane) (X)", "Asia Brickell"),
            #("Leonida Keys 01 (Airplane) (X)", "FAA Miami ATCT (MIA)"),
            #("Tennis Court (SE)", "The Waverly South Beach (NW)"),
            #("Sidewalk (Jason) (E)", "Flamingo South Beach (SRSW)"),
            ("Alley (W)", "Flamingo South Beach (TE)"),
            ("Alley (W)", "Flamingo South Beach (TNE)"),
            ("Alley (W)", "Flamingo South Beach (TSE)"),
            ("Sidewalk (Jason) (E)", "The Floridian"),
            ("Park", "Jenny Hostel (NE)"),
            ("Port", "Murano Grande"),
            ("Park", "1500 Ocean Dr"),
            ("Park", "1500 Ocean Dr (S) (SE)"),
            ("Tennis Court (SE)", "Old City Hall"),
            ("Tennis Court (SE)", "1000 Venetian Way (SW)"),
        ],
        #((2270-25, 1085-25), (2270+25, 1085+25)), 10, 1.0,
        #(55, 85), (-7.0, -3.9, 0.05), (55, 70, 0.05),
        ((2265-12, 1075-12), (2265+12, 1075+12)), 8, 1.0,
        (55, 85), (-6.0, -4.99, 0.01), (60, 65.01, 0.01),
        "yanis", 2, (1000, 0, 3000, 2000),
        None,
        "triangulate/vbb"
    )
    print("### UPDATE VICE BEACH CAMERA ###")


if sys.argv[1] == "-vcia":

    for cam_name_0, cam_name_1, lm_name in (
        ("Vice Beach (B)", "Leonida Keys 01 (Airplane) (X)", "Asia Brickell"),
        ("Vice Beach (B)", "Leonida Keys 01 (Airplane) (X)", "FAA Miami ATCT (MIA)"),
        ("Vice Beach (B)", "Alley (W)", "Flamingo South Beach (E)"),
        ("Vice Beach (B)", "Sidewalk (Jason) (E)", "The Floridian"),
        ("Vice Beach (B)", "Port", "Murano Grande"),
        ("Vice Beach (B)", "Park", "1500 Ocean Dr"),
        ("Vice Beach (B)", "Tennis Court (SE)", "Old City Hall"),
        ("Vice Beach (B)", "Prison", "Opera Tower"),
        ("Vice Beach (B)", "Prison", "Southeast Financial Center"),
        ("Vice Beach (B)", "Tennis Court (SE)", "1000 Venetian Way (SW)"),
        ("Vice Beach (B)", "Prison", "Wells Fargo Center"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')
    print("### UPDATE LANDMARKS ###")


if sys.argv[1] == "-rooftop":

    cam = ml.find_camera(
        "Rooftop Party",
        [
            #"Asia Brickell Key",
            "Flamingo South Beach (TE)",
            "Flamingo South Beach (TSE)",
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (BW)",
            #"Loews Miami Beach",
            "1500 Ocean Dr",
            "Old City Hall",
            "Portofino Tower (NW)",
        ],
        [
            ("Vice Beach (B)", "Capri South Beach (SE)"),
            #("Sidewalk (Jason) (E)", "Continuum on South Beach (S)"),
            #("Vice Beach (B)", "Cruise Terminal G (B)"),
            #("Venetian Islands", "Flagler Memorial Monument"),
            ("Vice Beach (B)", "Flamingo South Beach (NENE)"),
            ("Vice Beach (A)", "Loews Miami Beach"),
            ("Vice Beach (B)", "Royal Palm South Beach (S)"),
            ("Vice Beach (B)", "Royal Palm South Beach (N) (N)"),
            ("Vice Beach (B)", "The Waverly South Beach (SE)"),
        ],
        ((1920, 1960), (1920, 1960)), 25, 1,
        (80, 120), (-9.0, -5.9, 0.1), (51.0, 64.1, 0.1),
        "yanis", 1, (1000, 1000, 2500, 2500),
        None,
        "triangulate/rooftop"
    )


if sys.argv[1] == "-vi":

    cam, loss = ml.find_camera(
        "Venetian Islands",
        [
            "Flamingo South Beach (TNE)",
            "Loews Miami Beach",
            "1500 Ocean Dr",
            "1000 Venetian Way (SW)",
            #"Rooftop Party",
        ],
        [
            ("Highway (NE)", "Akoya Condominium"),
            ("Vice Beach (A)", "Flamingo South Beach (SDS)"),
            ("Sidewalk (Jason) (E)", "Flamingo South Beach (SRSW)"),
            #("Sidewalk (Jason) (E)", "Flamingo South Beach (TSW)"),
            ("Highway (NE)", "Jade Ocean Condos"),
            #("Vice Beach (A)", "Loews Miami Beach"),
            ("Vice Beach (B)", "1500 Ocean Dr (S) (NW)"),
            ("Park", "1500 Ocean Dr (S) (SW)"),
            ("Vice Beach (B)", "Royal Palm South Beach (N) (N)"),
            ("Vice Beach (B)", "Royal Palm South Beach (N) (S)"),
            ("Vice Beach (B)", "St. Moritz Hotel (SW)"),
        ],
        ((-25, 1090), (-75, 1090)), 20, 1,
        None, (-15.0, -12.4, 0.1), (62.0, 68.1, 0.1),
        "yanis", 1, (-1000, 0, 1000, 2000),
        (-500, 0, 3000, 3000),
        "triangulate/vi"
    )
    cam.register()
    print(cam)
    for cam_name, lm_name in (
        ("Highway (NE)", "Akoya Condominium"),
        ("Highway (NE)", "Jade Ocean Condos"),
    ):
        p, (x, y, z), b, d, _ = ml.find_landmark(cam.name, cam_name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam.name} & {cam_name}')
    lm_names = (
        "Biscayne Island (S)",
        "Di Lido Island (N)",
        "Di Lido Island (S)",
        "Flagler Memorial Island (N)",
        "Pelican Harbor Marina (A)",
        "Pelican Harbor Marina (B)",
        "Pelican Harbor Marina (C)",
        "Pelican Harbor Marina (D)",
        "Pelican Harbor Marina (E)",
        "Pier (Flamingo)",
        "Rivo Alto Island (S)",   
    )
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    print("### UPDATE CAMERA AND LANDMARKS ###")


if sys.argv[1] == "-beach":

    cam, loss = ml.find_camera(
        "Beach",
        [
            "Akoya Condominium",
            "Hotel Breakwater",
            "Jenny Hostel (NE)",
            "Loews Miami Beach",
            "1500 Ocean Dr",
            "1500 Ocean Dr (S) (SE)",
            "Royal Palm South Beach (N) (S)",
            "Royal Palm South Beach (S)",
        ],
        [
            ("Vice Beach (A)", "12th St Lifeguard Tower"),
            ("Venetian Islands", "Bank of America Financial Center"),
            ("Venetian Islands", "Green Diamond"),
            ("Park", "Hotel Victor (SW)"),
            ("Venetian Islands", "Jade Ocean Condos (SW)"),
            ("Vice Beach (B)", "The Tides South Beach"),
            ("Venetian Islands", "Trésor Tower"),
        ],
        ((2220, -390), (2220, -390)), 25, 1,
        (1.0, 3.0), (-1.5, -0.4, 0.1), (30, 45.1, 0.1),
        "yanis", 1, (1000, -1000, 3000, 1000),
        None,
        "triangulate/beach"
    )
    cam.register()
    lm_names = (
        "Beach (A)", "Beach (B)", "Beach (C)",
        "Beach (D)", "Beach (E)", "Beach (F)",
    )
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')


if sys.argv[1] == "-skyline":

    x, y = 800, 1350
    #x, y = 755, 1335
    cam, loss = ml.find_camera(
        "Skyline",
        [
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (NW)",
            "1000 Venetian Way (SE)"
        ],
        [
            ("Vice Beach (B)", "Asia Brickell Key"),
            ("Vice Beach (B)", "Flagler on the River"),
            ("Vice Beach (B)", "The Grand (E)"),
            ("Vice Beach (B)", "Loft Downtown II"),
            ("Vice Beach (B)", "Marina Blue (NE)"),
            ("Vice Beach (B)", "Opera Tower"),
            ("Vice Beach (B)", "Southeast Financial Center"),
            ("Vice Beach (B)", "Ten Museum Park (SE)"),
            #("Vice Beach (B)", "1000 Venetian Way (SE)"),
            #("Venetian Islands", "1000 Venetian Way (2)"),
            #("Venetian Islands", "1000 Venetian Way (3)"),
            ("Venetian Islands", "1000 Venetian Way (4)"),
            ("Vice Beach (B)", "Wells Fargo Center (N)"),
        ],
        ((x, y), (x, y)), 25, 1,
        (10, 25), (-3.0, -0.9, 0.1), (50, 70, 0.1),
        "yanis", 1, (x - 500, y - 500, x + 500, y + 500),
        None,
        "triangulate/skyline"
    )


if sys.argv[1] == "-basketball":
    cam, loss = ml.find_camera(
        "Vice City 03 (Basketball)",
        [
            #"Capri South Beach (SE)",
            #"Flamingo South Beach (NENE)",
            "The Grand (E)",
            "Loft Downtown II",
            "Marina Blue (NE)",
            "Opera Tower",
            "Southeast Financial Center",
            "Wells Fargo Center (N)",
        ],
        [
            ("Skyline", "50 Biscayne Blvd (SE)"),
            ("Hotel (W)", "Brown Hotel Sign"),
            ("Skyline", "Citigroup Center (NW)"),
            ("Skyline", "Citigroup Center (SE)"),
            #("Rooftop Party", "Flamingo South Beach (NWNE)"),
            #("Venetian Islands", "The Gates Hotel South Beach (NW)"),
            #("Rooftop Party", "1111 Lincoln Rd (NW)"),
            #("Rooftop Party", "1111 Lincoln Rd (SE)"),
            ("Vice Beach (B)", "Marriott Miami Biscayne Bay (NE)"),
            #("Venetian Islands", "New World Center"),
            ("Skyline", "One Miami Condominium East (NE)"),
            ("Skyline", "One Miami Condominium East (SE)"),
            ("Skyline", "One Miami Condominium West (NE)"),
            ("Skyline", "One Miami Condominium West (SE)"),
            ("Vice Beach (B)", "Quantum on the Bay Condominium (N) (NE)"),
            ("Vice Beach (B)", "Quantum on the Bay Condominium (S) (NE)"),
            #("Venetian Islands", "Sunset Harbour South Condo"),
            #("Venetian Islands", "Sunset Harbour South Condo (RN)"),
            #("Venetian Islands", "Sunset Harbour South Condo (RS)"),
            ("Vice Beach (B)", "Venetian Isle Condominium"),
            ("Rooftop Party", "W South Beach (BNW)"),
        ],
        ((1987, 1659), (1987, 1659)), 3, 1,
        (35, 70), (-11.0, -6.9, 0.1), (50, 60.1, 0.1),
        "yanis", 1, (1000, 500, 3000, 2500),
        None,
        "triangulate/basketball"
    )
    cam.register()
    lm_names = (
        "Canal (Hotel Valetta)",
        "Rivo Alto Island (N)",
        "Marina (Stockyard) (NE)",
    )
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')


if sys.argv[1] == "-vcp":

    """
    cam, loss = ml.find_camera(
        "Vice City Postcard",
        [
            "Asia Brickell Key",
            "Citigroup Center (NW)",
            "Four Seasons Hotel Miami (BW)",
            "Four Seasons Hotel Miami (NW)",
            "The Grand (E)",
            "Marriott Miami Biscayne Bay (NE)",
            "One Miami Condominium East (NE)",
            "One Miami Condominium West (NE)",
            "Opera Tower",
            "Quantum on the Bay Condominium (N) (NE)",
            "Quantum on the Bay Condominium (S) (NE)",
            "Southeast Financial Center",
            "1000 Venetian Way (SE)",
            "Venetian Isle Condominium",
            "Wells Fargo Center (N)",
        ],
        [
            ("Vice City 03 (Basketball)", "1800 Club"),
            ("Vice City 03 (Basketball)", "22 Biscayne Bay (SE)"),
            ("Skyline", "Carbonell Brickell"),
            ("Vice City 03 (Basketball)", "Citigroup Center (NE)"),
            ("Vice City 03 (Basketball)", "The Crimson (CC)"),
            #("Ambrosia 02 (Panorama)", "Flat Water Tower"),
            ("Vice City 03 (Basketball)", "InterContinental Miami (N)"),
            ("Skyline", "Kaseya Center (SE)"),
            #("Sidewalk (Jason) (E)", "Margaret Pace Park"),
            ("Vice City 03 (Basketball)", "Marriott Miami Biscayne Bay (E)"),
            ("Vice City 03 (Basketball)", "Marriott Miami Biscayne Bay (NE)"),
            ("Skyline", "Miami Tower"),
            ("Vice City 03 (Basketball)", "419 NE 4th Ave (W)"),
            ("Vice City 03 (Basketball)", "New Wave Condominiums"),
            ("Vice City 03 (Basketball)", "Quantum on the Bay Condominium (N) (NE)"),
            ("Vice City 03 (Basketball)", "Quantum on the Bay Condominium (S) (NE)"),
            #("Intersection (W)", "Reworld Miami-Dade (SE)"),
            ("Skyline", "Skyviews Miami Observation Wheel"),
            ("Vice Beach (B)", "Three Tequesta Point"),
            ("Vice Beach (B)", "Two Tequesta Point"),
            #("Vice Beach (B)", "Unknown Building near VCIA (N)"),
            #("Vice Beach (B)", "Unknown Building near VCIA (S)"),
            ("Vice City 03 (Basketball)", "Uptown Lofts (NE)"),
            ("Vice City 03 (Basketball)", "Uptown Lofts (SE)"),
            ("Skyline", "Unknown Sphere"),
            ("Vice Beach (B)", "1000 Venetian Way (SW)"),
            ("Vice City 03 (Basketball)", "Vizcayne North Condominium (SE)"),
            ("Vice City 03 (Basketball)", "Vizcayne North Condominium (NE)"),
            #("Sidewalk (Jason) (E)", "West Venetian Causeway Bridge"),
        ],
        ((400, 1890), (400, 1890)), 25, 1,
        #((365.0, 1835.0), (375.0, 1885.0)), 15, 1.0,
        (25, 50), (1.5, 4.6, 0.1), (55, 75, 0.1),
        #None, (1.0, 5.1, 0.1), (55, 85, 0.1),
        "yanis", 1, (-500, 1000, 1000, 2500),
        (-1000, 0, 1000, 2000),
        "triangulate/vcp"
    )
    """
    cam, loss = ml.find_camera(
        "Vice City Postcard",
        [
            "Four Seasons Hotel Miami (BW)",
            "Four Seasons Hotel Miami (NW)",
            "The Grand (E)",
            "1000 Venetian Way (SE)",
        ],
        [
            ("Vice Beach (B)", "Asia Brickell Key"),
            ("Vice City 03 (Basketball)", "1800 Club"),
            ("Vice City 03 (Basketball)", "22 Biscayne Bay (SE)"),
            ("Skyline", "Carbonell Brickell"),
            ("Vice City 03 (Basketball)", "Citigroup Center (NE)"),
            ("Vice City 03 (Basketball)", "Citigroup Center (NW)"),
            ("Vice City 03 (Basketball)", "The Crimson (CC)"),
            #("Ambrosia 02 (Panorama)", "Flat Water Tower"),
            ("Vice City 03 (Basketball)", "InterContinental Miami (N)"),
            ("Skyline", "Kaseya Center (SE)"),
            #("Sidewalk (Jason) (E)", "Margaret Pace Park"),
            ("Vice City 03 (Basketball)", "Marriott Miami Biscayne Bay (E)"),
            ("Vice Beach (B)", "Marriott Miami Biscayne Bay (NE)"),
            ("Vice Beach (B)", "Opera Tower"),
            ("Skyline", "Miami Tower"),
            ("Vice City 03 (Basketball)", "419 NE 4th Ave (W)"),
            ("Vice City 03 (Basketball)", "New Wave Condominiums"),
            ("Vice City 03 (Basketball)", "One Miami Condominium East (NE)"),
            ("Vice City 03 (Basketball)", "One Miami Condominium West (NE)"),
            ("Vice Beach (B)", "Quantum on the Bay Condominium (N) (NE)"),
            ("Vice Beach (B)", "Quantum on the Bay Condominium (S) (NE)"),
            #("Intersection (W)", "Reworld Miami-Dade (SE)"),
            ("Vice Beach (B)", "Southeast Financial Center"),
            ("Skyline", "Skyviews Miami Observation Wheel"),
            ("Vice Beach (B)", "Three Tequesta Point"),
            ("Vice Beach (B)", "Two Tequesta Point"),
            #("Vice Beach (B)", "Unknown Building near VCIA (N)"),
            #("Vice Beach (B)", "Unknown Building near VCIA (S)"),
            ("Vice City 03 (Basketball)", "Uptown Lofts (NE)"),
            ("Vice City 03 (Basketball)", "Uptown Lofts (SE)"),
            ("Skyline", "Unknown Sphere"),
            ("Vice Beach (B)", "Venetian Isle Condominium"),
            ("Vice Beach (B)", "1000 Venetian Way (SW)"),
            ("Vice City 03 (Basketball)", "Vizcayne North Condominium (SE)"),
            ("Vice City 03 (Basketball)", "Vizcayne North Condominium (NE)"),
            ("Vice Beach (B)", "Wells Fargo Center (N)"),
            #("Sidewalk (Jason) (E)", "West Venetian Causeway Bridge"),
        ],
        ((400, 1860), (400, 1860)), 25, 1,
        #((365.0, 1835.0), (375.0, 1885.0)), 15, 1.0,
        (25, 50), (1.5, 4.6, 0.1), (55, 75, 0.1),
        #None, (1.0, 5.1, 0.1), (55, 85, 0.1),
        "yanis", 1, (-500, 1000, 1000, 2500),
        (-1000, 0, 1000, 2000),
        "triangulate/vcp"
    )
    cam.register()
    lm_names = (
        "Picnic Island A (N)",
        "Picnic Island B (S)",
        "Picnic Island C (S)",
        "Marina (Stockyard) (NE)",
        "Marina (Stockyard) (SE)",
        "Marina (Stockyard) (SW)",
    )
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')


if sys.argv[1] == "-motorboats":

    cam = ml.get_camera("Motorboats (A)")
    cam.test_lines()

    #hfov = 60
    #hfov = 64
    hfov = 63
    cx, cy = {
        60: (1600, -730),
        63: (1524, -790),
        64: (1490, -810)
    }[hfov]

    #"""
    cam, loss = ml.find_camera(
        "Motorboats (A)",
        [
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (SE)",
            "Park Grove Condominium (S)"
        ],
        [
            ("Vice Beach (B)", "Asia Brickell Key (CC1)"),
            ("Vice Beach (B)", "Asia Brickell Key (CC2)"),
        ],
        ((cx, cy), (cx, cy)), 25, 1,
        (1.5, 2.5), (1.5, 2.5, 0.01), (hfov, hfov + 0.09, 0.1), # (60, 65, 0.1),
        "yanis", 1, (cx - 500, cy - 500, cx + 500, cy + 500),
        None,
        "triangulate/motorboats_a" 
    )
    #"""

    # container_height = 2.591
    container_height = 2.99
    target_height = 4 * container_height
    lm_t, lm_b = "Stack (T)", "Stack (B)"
    d = 100
    while True:
        point_b = ml.get_point(cam.xyz, cam.get_landmark_direction(lm_b), d)
        point_t = ml.intersect_ray_and_ray(
            (cam.xyz, cam.get_landmark_direction(lm_t)),
            (point_b, (0, 0, 1))
        )[0]
        current_height = point_t[2] - point_b[2]
        if current_height >= target_height:
            point_c = (point_b[0], point_b[1], 2)
            distance = ml.get_distance(cam.xyz, point_c)
            break
        d += 0.001
    print(f"{distance=:.3f}")
    x, y, z = point_t
    print(f'    "{lm_t}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')

    filename = "triangulate/motorboats_a markup.png"
    if not os.path.exists(filename):
        color = ml.get_color("C")
        for edge in ("TS", "BS", "BN"):
            landmarks = [f"C ({edge}{corner})" for corner in "EW"]
            cam.draw_line((
                cam.landmark_pixels[landmarks[0]],
                cam.landmark_pixels[landmarks[1]]
            ), fill=color, width=1)
        for edge in ("BW", "BE", "TE"):
            landmarks = [f"C ({edge[0]}{corner}{edge[1]})" for corner in "SN"]
            cam.draw_line((
                cam.landmark_pixels[landmarks[0]],
                cam.landmark_pixels[landmarks[1]]
            ), fill=color, width=1)
        for edge in ("SW", "SE", "NE"):
            landmarks = [f"C ({corner}{edge})" for corner in "TB"]
            cam.draw_line((
                cam.landmark_pixels[landmarks[0]],
                cam.landmark_pixels[landmarks[1]]
            ), fill=color, width=1)
        cam.render_all()
        cam.save(filename)

    target_height = container_height
    points = {}
    for edge in ("NE", "SE", "SW"):
        lm_t, lm_b = [f"C ({corner}{edge})" for corner in "TB"]
        d = 25
        while True:
            point_b = ml.get_point(cam.xyz, cam.get_landmark_direction(lm_b), d)
            point_t = ml.intersect_ray_and_ray(
                (cam.xyz, cam.get_landmark_direction(lm_t)),
                (point_b, (0, 0, 1))
            )[0]
            current_height = point_t[2] - point_b[2]
            if current_height >= target_height:
                points[f"C (T{edge})"] = point_t
                points[f"C (B{edge})"] = point_b
                break
            d += 0.001
    #points["C (TSW)"] = (points["C (TSW)"][0], points["C (TSW)"][1], points["C (TSE)"][2])
    #points["C (BSW)"] = (points["C (BSW)"][0], points["C (BSW)"][1], points["C (BSE)"][2])
    dir_west = ml.get_direction(points["C (BSE)"], points["C (BSW)"])
    bearing_west = ml.get_angles_from_direction(dir_west)[0]
    bearing_north = (bearing_west - 90) % 360
    print(f"{bearing_west=:.3f} {bearing_north=:.3f}")
    dir_north = ml.get_direction_from_angles(bearing_north, 0)
    points["C (BNE)"] = ml.intersect_ray_and_ray(
        (points["C (BSE)"], dir_north),
        (cam.xyz, cam.get_landmark_direction("C (BNE)"))
    )[1]
    points["C (TNE)"] = ml.intersect_ray_and_ray(
        (points["C (TSE)"], dir_north),
        (cam.xyz, cam.get_landmark_direction("C (TNE)"))
    )[1]
    for edge in ("NE", "SE", "SW"):
        lm_t, lm_b = [f"C ({corner}{edge})" for corner in "TB"]
        x, y, z = points[lm_t]
        print(f'    "{lm_t}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
        x, y, z = points[lm_b]
        print(f'    "{lm_b}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    width = (
        ml.get_distance(points["C (TSE)"], points["C (TNE)"]) +
        ml.get_distance(points["C (BSE)"], points["C (BNE)"])
    ) / 2
    height = (
        ml.get_distance(points["C (BSE)"], points["C (TSE)"]) +
        ml.get_distance(points["C (BNE)"], points["C (TNE)"]) +
        ml.get_distance(points["C (BSW)"], points["C (TSW)"])
    ) / 3
    depth = (
        ml.get_distance(points["C (TSE)"], points["C (TSW)"]) +
        ml.get_distance(points["C (BSE)"], points["C (BSW)"])
    ) / 2
    print(f"{height=:.3f} {width=:.3f} {depth=:.3f}")
    east = ml.get_midpoint([points["C (TSE)"], points["C (BSE)"], points["C (TNE)"], points["C (BNE)"]])
    south = ml.get_midpoint([points["C (TSW)"], points["C (BSW)"], points["C (TSE)"], points["C (BSE)"]])
    center = ml.intersect_ray_and_ray(
        (east, dir_west),
        (south, dir_north)
    )[0]
    x, y, z = center
    print(f"center=({x:.3f}, {y:.3f}, {z:.3f})")

    cam = ml.get_camera(cam.name)
    color = ml.get_color("C")
    for point in points.values():
        cam.render_box(point, (1, 1, 1), 0, fill=color, width=1)
    cam.render_box(center, (width, depth, height), bearing_west, fill=color, width=2)
    color = ml.get_color("CC")
    cam.draw_line((cam.landmark_pixels["CC (3) (BB1)"], cam.landmark_pixels["CC (3) (BB3)"]), fill=color, width=1)
    cam.render_all()
    lm_names = ("C (BSE)", "CC (4) (BB)", "CC (3) (BB2)", "Container Crane (3)")
    for i, lm_name in enumerate(lm_names[:-1]):
        cam.draw_line((cam.landmark_pixels[lm_name], cam.landmark_pixels[lm_names[i + 1]]), fill=(255, 255, 0), width=1)
    cam.save("triangulate/motorboats_a container.png")

    lm_name = "CC (4) (BB)"
    points[lm_name] = ml.intersect_ray_and_ray(
        (points["C (BSE)"], (0, 0, 1)),
        (cam.xyz, cam.get_landmark_direction(lm_name))
    )[1]
    x, y, z = points[lm_name]
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')

    lm_name = "CC (3) (BB2)"
    points[lm_name] = ml.intersect_ray_and_plane(
        (cam.xyz, cam.get_landmark_direction(lm_name)),
        ((0, 0, z), (0, 0, 1))
    )
    x, y, z = points[lm_name]
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')

    lm_name = "Container Crane (3)"
    points[lm_name] = ml.intersect_ray_and_ray(
        (cam.xyz, cam.get_landmark_direction(lm_name)),
        (points["CC (3) (BB2)"], (0, 0, 1))
    )[1]
    x, y, z = points[lm_name]
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    md.landmarks[lm_name] = (x, y, z)

    lm_name = "Container Crane (1)"
    points[lm_name] = ml.intersect_ray_and_plane(
        (cam.xyz, cam.get_landmark_direction(lm_name)),
        ((0, 0, z), (0, 0, 1))
    )
    x, y, z = points[lm_name]
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    md.landmarks[lm_name] = (x, y, z)

    cam, loss = ml.find_camera(
        "Motorboats (B)",
        [
            "Container Crane (1)",
            "Container Crane (3)",
            "Four Seasons Hotel Miami (BE)",
            "Four Seasons Hotel Miami (SE)",
            "Park Grove Condominium (S)"
        ],
        [
            ("Vice Beach (B)", "Asia Brickell Key (CC1)"),
            ("Vice Beach (B)", "Asia Brickell Key (CC2)"),
            ("Vice City 03 (Basketball)", "Marina Blue (NE)"),
            ("Vice City 03 (Basketball)", "Vizcayne North Condominium (NE)"),
        ],
        ((cx, cy), (cx, cy)), 25, 1,
        #((1700, -800), (1700, -900)), 10, 1,
        (1.5, 2.5), (-3.0, 0.1, 0.01), (hfov, hfov + 0.09, 0.1), #(55, 70.1, 0.1),
        "yanis", 1, (cx - 500, cy - 500, cx + 500, cy + 500),
        None,
        "triangulate/motorboats_b"
    )

    """
    container_height = 2.591
    target_height = 4 * container_height
    lm_t, lm_b = "Stack (T)", "Stack (B)"
    d = 100
    while True:
        point_b = ml.get_point(cam.xyz, cam.get_landmark_direction(lm_b), d)
        point_t = ml.intersect_ray_and_ray(
            (cam.xyz, cam.get_landmark_direction(lm_t)),
            (point_b, (0, 0, 1))
        )[0]
        current_height = point_t[2] - point_b[2]
        if current_height >= target_height:
            point_c = (point_b[0], point_b[1], 2)
            distance = ml.get_distance(cam.xyz, point_c)
            break
        d += 0.001
    print(f"{distance=:.3f}")
    """

    z = md.landmarks["Container Crane (1)"][2]
    lm_name = "Container Crane (2)"
    points[lm_name] = ml.intersect_ray_and_plane(
        (cam.xyz, cam.get_landmark_direction(lm_name)),
        ((0, 0, z), (0, 0, 1))
    )
    x, y, z = points[lm_name]
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    md.landmarks[lm_name] = (x, y, z)

    m = ml.get_map("yanis")
    x, y = ml.get_camera("Motorboats (A)").xy
    area = (x - 1000, y - 500, x + 1000, y + 500)
    m.draw_all().save("triangulate/motorboats map.png", area)


if sys.argv[1] == "-ferriswheel":

    cam = ml.get_camera("Vice City 08 (Ferris Wheel)")
    x, y = cam.xy
    x, y = -575.000, 925.000
    cam, loss = ml.find_camera(
        "Vice City 08 (Ferris Wheel)",
        [
            "Container Crane (1)",
            "Container Crane (2)",
            "Container Crane (3)",
            "CC (1) (BB2)",
            "CC (2) (BB2)",
            "CC (3) (BB2)",
            "Kaseya Center (SE)",
            "Skyviews Miami Observation Wheel",
        ],
        [
            ("Skyline", "Cruise Ship (FT)"),
            ("Vice City Postcard", "Cruise Ship (RT)"),
            #("Leonida Keys Postcard (X)", "WTP (E)"),
            #("Leonida Keys Postcard (X)", "WTP (W)"),
        ],
        ((x, y), (x, y)), 25, 1,
        (60, 110), (-14.0, -5.9, 0.1), (30, 50.1, 0.1),
        "yanis", 1, (x - 1000, y - 1000, x + 1000, y + 1000),
        (-1000, -2500, 2500, 1000),
        "triangulate/ferriswheel"
    )

    for letter in "CDEFGHIJKL":
        lm_name = f"Port ({letter})"
        x, y, z =cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')


if sys.argv[1] == "-convertible":

    cam = ml.get_camera("Convertible")
    x, y = cam.xy
    cam, loss = ml.find_camera(
        "Convertible",
        [
            "Kaseya Center (SE)",
        ],
        [
            ("Vice City 08 (Ferris Wheel)", "Highway Sign (S)"),
            ("Vice City 08 (Ferris Wheel)", "KC01"),
            ("Vice City 08 (Ferris Wheel)", "KC02"),
            ("Vice City 08 (Ferris Wheel)", "KC03"),
            ("Vice City 08 (Ferris Wheel)", "KC04"),
            ("Vice City 08 (Ferris Wheel)", "KC06"),
            ("Vice City 08 (Ferris Wheel)", "KC07"),
            ("Vice City 08 (Ferris Wheel)", "KC08"),
            ("Vice City 08 (Ferris Wheel)", "KC09"),
            ("Vice City 08 (Ferris Wheel)", "KC10"),
            ("Vice City 08 (Ferris Wheel)", "KC11"),
            #("Vice Beach (B)", "Ten Museum Park (SE)"),
        ],
        ((x, y), (x, y)), 500, 20,
        (10, 30), (-5.0, 0.1, 0.1), (30, 90.1, 1.0),
        "yanis", 1, (x - 1000, y - 1000, x + 1000, y + 1000),
        None,
        "triangulate/convertible"
    )


if sys.argv[1] == "-rb03":

    fs = ml.FS
    fs16e = (fs.fs40e[0], fs.fs40e[1], fs.fs40e[2] - 24 * fs.floor_height)
    fs16ne = (fs.fs40ne[0], fs.fs40ne[1], fs.fs40ne[2] - 24 * fs.floor_height)
    fs24e = (fs.fs40e[0], fs.fs40e[1], fs.fs40e[2] - 16 * fs.floor_height)
    fs24ne = (fs.fs40ne[0], fs.fs40ne[1], fs.fs40ne[2] - 16 * fs.floor_height)
    md.landmarks["Four Seasons Hotel Miami (16E)"] = fs16e
    md.landmarks["Four Seasons Hotel Miami (16NE)"] = fs16ne
    md.landmarks["Four Seasons Hotel Miami (24E)"] = fs24e
    md.landmarks["Four Seasons Hotel Miami (24NE)"] = fs24ne
    cam, loss = ml.find_camera(
        "Raul Bautista 03 (Motorboat)",
        [
            "Four Seasons Hotel Miami (16E)",
            "Four Seasons Hotel Miami (16NE)",
            "Four Seasons Hotel Miami (24E)",
            "Four Seasons Hotel Miami (24NE)",
        ],
        [
            ("Vice City 03 (Basketball)", "One Miami Condominium East (SE)"),
            ("Vice City 03 (Basketball)", "One Miami Condominium West (SE)"),
        ],
        #((-750, -2000), (-750, -2000)), 250, 10,
        ((-750, -1890), (-750, -1890)), 25, 1,
        (0, 2.5), (-1.0, 0.1, 0.1), (45, 70.1, 0.1),
        "yanis", 1, (-1750, -2750, 250, -750),
        None,
        "triangulate/rb03"
    )    


if sys.argv[1] == "-hpba":

    cam, loss = ml.find_camera(
        "Highway (Peacock Bay) (A)",
        [
            "Park Grove Condominium (N)",
            "Park Grove Condominium (C)",
        ],
        [
            ("Metro (SE) (B)", "Infinity at Brickell"),
            ("Grassrivers 02 (Watson Bay)", "One Broadway (W)"),
            ("Vice City 03 (Basketball)", "Stephen P. Clark Government Center (E)")
        ],
        ((-1480.000, -2370.000), (-1480.000, -2370.000)), 25, 1,
        (15, 35), (0.0, 5.0, 0.1), (45.0, 60.0, 0.1),
        "yanis", 1, (-2000, -2500, 0, -500),
        None,
        "triangulate/highway_peacock_bay_a"
    )


if sys.argv[1] == "-hpbb":

    fake_cam_name = "Four Seasons Fake Cam"
    bearing = ml.get_bearing(
        md.landmarks["Four Seasons Hotel Miami (BE)"][:2],
        md.landmarks["Four Seasons Hotel Miami (BW)"][:2],
    )
    print(f"four seasons fake cam {bearing=}")
    md.cameras[fake_cam_name] = {
        "id": "X",
        "player": None,
        "xyz": md.landmarks["Four Seasons Hotel Miami (BE)"],
        "ypr": (bearing, 0, 0),
        "fov": (90, None),
        "size": (3840, 2160),
        "source": ""
    }
    md.pixels[fake_cam_name] = {
        "Four Seasons Hotel Miami (T)": (1920, 1080)
    }
    cam, loss = ml.find_camera(
        "Highway (Peacock Bay) (B)",
        [
            "Park Grove Condominium (N)",
            "Park Grove Condominium (C)",
        ],
        [
            ("Four Seasons Fake Cam", "Four Seasons Hotel Miami (T)"),
            ("Metro (SE) (B)", "Infinity at Brickell"),
            ("Grassrivers 02 (Watson Bay)", "One Broadway (W)"),
            ("Vice City 03 (Basketball)", "Stephen P. Clark Government Center (E)")
        ],
        #((-1500.000, -2300.000), (-1500.000, -2300.000)), 250, 10,
        ((-1464.000, -2264.000), (-1464.000, -2264.000)), 25, 1.0,
        (15, 35), (10.0, 20.0, 0.1), (50.0, 60.0, 0.1),
        "yanis", 1, (-2000, -2500, 0, 500),
        None,
        "triangulate/highway_peacock_bay_b"
    )


### AMBROSIA (FIXME: remove?)

if sys.argv[1] == "-ambrosia_panorama":

    fake_cam_name = "WDNA FM Fake Cam"
    md.cameras[fake_cam_name] = {
        "id": "X",
        "player": None,
        "xyz": md.landmarks["WDNA FM"],
        "ypr": (0, -89.999, 0),
        "fov": (90, None),
        "size": (3840, 2160)
    }
    md.pixels[fake_cam_name] = {
        "WDNA FM (B)": (1920, 1080)
    }

    cam, loss = ml.find_camera(
        "Ambrosia 02 (Panorama)",
        [
            "FAA Miami ATCT (MIA)"
        ],
        [
            ("Leonida Keys 01 (Airplane) (X)", "MIA North Terminal Tower"),
            ("Loading Zone near Prison (SW)", "Water Tower near Prison"),
            ("WDNA FM Fake Cam", "WDNA FM (B)"),
            ("Leonida Keys 01 (Airplane) (X)", "Wheelabrator South Broward"),
        ],
        ((-2475, 4500), (-2475, 5500)), 25, 2,
        (10, 110), (-4.0, -1.9, 0.1), (40.0, 60.1, 0.1),
        "yanis", 1, (-4000, 3000, -1000, 7000),
        (-4000, 3000, -1000, 7000),
        "triangulate/ambrosia_panorama"
    )


if sys.argv[1] == "-ambrosia_fires":

    cam, loss = ml.find_camera(
        "Ambrosia 04 (Fires)",
        [
            "Sunshine Skyway Bridge (N)",
            "Sunshine Skyway Bridge (S)",
        ],
        [
            ("Ambrosia 02 (Panorama)", "Sebring Water Tower (B)"),
            ("Ambrosia 02 (Panorama)", "Sebring Water Tower (T)"),
            ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Tank)"),
            ("Ambrosia 02 (Panorama)", "US Sugar Mill (Factory)"),
            ("Ambrosia 02 (Panorama)", "USSM Smokestack (4)"),
            ("Ambrosia 02 (Panorama)", "USSM Smokestack (5)"),
            ("Ambrosia 02 (Panorama)", "USSM Smokestack (6)"),
            ("Ambrosia 02 (Panorama)", "USSM Smokestack (7)"),
            ("Ambrosia 02 (Panorama)", "USSM Smokestack (8)"),
            ("Ambrosia 02 (Panorama)", "USSM Smokestack (9)"),
            ("Ambrosia 02 (Panorama)", "Wheelabrator South Broward (W)"),
        ],
        ((-2000-750, 5000), (-1500-750, 3500)), 250, 10,
        (25, 75), (-5.0, -0.9, 0.2), (60.0, 86.1, 0.2),
        "yanis", 1, (-3250, 2000, -1250, 6000),
        None,
        "triangulate/ambrosia_fires"
    )


if sys.argv[1] == "-ambrosia_fires_test":

    cam_0_name = "Ambrosia 02 (Panorama)"
    cam_1_name = "Ambrosia 04 (Fires)"
    cam_0 = ml.get_camera(cam_0_name)
    cam_1 = ml.get_camera(cam_1_name)
    cam_0_rel_xyz = (340.321, 940.126, 68.543)
    cam_0_rel_ypr = (170.555, -3.831, 0.000)
    cam_1_rel_xyz = (501.142, 29.554, 50.000)
    cam_1_rel_ypr = (99.023, -4.456, 0.000)
    dir_0_1_rel = ml.get_direction(cam_0_rel_xyz, cam_1_rel_xyz)
    bearing_0_1_rel, elevation_0_1_rel = ml.get_angles_from_direction(dir_0_1_rel)
    bearing_0_1_abs = bearing_0_1_rel - cam_0_rel_ypr[0] + cam_0.yaw
    elevation_0_1_abs = elevation_0_1_rel - cam_0_rel_ypr[1] + cam_0.pitch
    dir_0_1_abs = ml.get_direction_from_angles(bearing_0_1_abs, elevation_0_1_abs)
    print(f"{bearing_0_1_rel=} {bearing_0_1_abs=}")
    print(f"{elevation_0_1_rel=} {elevation_0_1_abs=}")
    cam_1.set_ypr((
        cam_1_rel_ypr[0] - bearing_0_1_rel + bearing_0_1_abs,
        cam_1.pitch,
        cam_1.roll
    ))
    print(cam_1)

    lm_name = "Sunshine Skyway Bridge (N)"
    lm_xyz = md.landmarks[lm_name]
    best_loss = float("inf")
    for dist in range(500, 10000, 1):
        cam_1_abs_xyz = ml.get_point(cam_0.xyz, dir_0_1_abs, dist)
        cam_1.set_xyz(cam_1_abs_xyz)
        p, d, a = ml.intersect_ray_and_point(
            (cam_1.xyz, cam_1.get_landmark_direction(lm_name)),
            lm_xyz
        )
        if a < best_loss:
            best_loss = a
        else:
            break
    print(dist, cam_1)
    cam_1.register()
    m = ml.get_map("yanis").draw_all()
    m.save("triangulate/ambrosia_fires_test map.png", (-8000, 0, 0, 8000))
    cam_1.render_all().save("triangulate/ambrosia_fires_test camera.png")


### PORT GELLHORN

if sys.argv[1] == "-aiwe":

    cam = mu.find_aiwe()
    
    cam.register()
    for lm_name, pixel in sorted(cam.landmark_pixels.items(), key=lambda kv: kv[0]):
        x, y, z = cam.get_point_at_zero_elevation(pixel)
        z = 10
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    print(cam)
    print("### UPDATE ###")


if sys.argv[1] == "-diner":

    cam_wa = ml.get_camera("Diner (W) (A)")
    cam_wb = ml.get_camera("Diner (W) (B)")
    cam_nw = ml.get_camera("Diner (NW)")
    cam_n = ml.get_camera("Diner (N)")
    cam_ne = ml.get_camera("Diner (NE)")
    cam_e = ml.get_camera("Diner (E)")
    cam_sea = ml.get_camera("Diner (SE) (A)")
    cam_seb = ml.get_camera("Diner (SE) (B)")
    cam_s = ml.get_camera("Diner (S)")
    cam_sw = ml.get_camera("Diner (SW)")
    cam_ei = ml.get_camera("Easy Inn")
    cam_cw = ml.get_camera("Car Wash")

    crane_height = 74.5
    crane_bb_height = 40.5

    print("\nDiner (W) (A)")
    m = ml.get_map("yanis")
    lm_name = "Sunshine Skyway Bridge (N)"
    point = ml.get_point(cam_wa.xyz, cam_wa.get_landmark_direction(lm_name), 10000)
    m.draw_line((cam_wa.xyz, point), ml.get_color(lm_name), 1)
    for i, pitch in enumerate(np.arange(-9.6, -8.79, 0.1)):
        filename = f"triangulate/diner wa pitch={pitch:.3f}.png"
        cam = ml.get_camera(cam_wa.name).open()
        cam.set_ypr((cam.yaw, pitch, cam.roll))
        if not os.path.exists(filename):
            cam.render_player().render_vertical_lines().render_distance_circles().render_camera_info()
            cam.save(filename)

        color = ml.get_rgb(i * 40, 1, 0.75)
        number = f"{pitch:.1f}"[-1]
        letters = "ABCDEFG"
        points = [
            cam.get_point_at_zero_elevation(cam.landmark_pixels[f"Bay ({letter}{letter})"])
            for letter in letters
        ]
        for i, letter in enumerate(letters):
            if letter in "CEG": continue
            m.draw_line((points[i], points[i + 1]), color, 1)
        for i, letter in enumerate(letters):
            m.draw_circle(points[i], 5, color, (255, 255, 255), 1, number)
        for crane_number in "23":
            crane = ml.intersect_ray_and_plane(
                (cam.xyz, cam.get_landmark_direction(f"Port of Tampa Container Crane ({crane_number})")),
                ((0, 0, crane_height), (0, 0, 1))
            )
            m.draw_circle(crane, 10, color, (255, 255, 255), 1, number)
    m.save("triangulate/diner pitch map.png", md.map_sections["Port Gellhorn"])

    yaw, pitch = 53.0, -9.2
    cam_wa.set_ypr((yaw, pitch, cam_wa.roll))
    cam_wa.test_lines()
    cam_wa.render_pixels().render_vertical_lines().render_vanishing_points().render_camera_info()
    cam_wa.save("triangulate/diner wa markup.png")

    """
    lm_names = ("Port of Tampa Container Crane (2)", "Port of Tampa Container Crane (3)")
    color = ml.get_color(lm_names[0])
    m = ml.get_map("yanis")
    for lm_name in lm_names:
        for height in range(70, 101, 10):
            point = ml.intersect_ray_and_plane(
                (cam_wb.xyz, cam_w.get_landmark_direction(lm_name)),
                ((0, 0, height), (0, 0, 1))
            )
            letter = str(height)[0]
            m.draw_circle(point, 10, fill=color, outline=(255, 255, 255), width=1, text=letter)
    lm_names = ("Bay (E)", "Bay (F)")
    landmarks = [md.landmarks[lm_name] for lm_name in lm_names]
    color = ml.get_color(lm_names[0])
    m.draw_line((landmarks[0], landmarks[1]), fill=color, width=1)
    for i, landmark in enumerate(landmarks):
        m.draw_circle(landmark, 10, fill=color, outline=(255, 255, 255), width=1, text="EF"[i])
    m.save("triangulate/diner w map crane.png", md.map_sections["Port Gellhorn"])
    """

    print(cam_wa)
    lm_names = ("Port of Tampa Container Crane (2)", "Port of Tampa Container Crane (3)")
    for lm_name in lm_names:
        x, y, z = ml.intersect_ray_and_plane(
            (cam_wa.xyz, cam_wa.get_landmark_direction(lm_name)),
            ((0, 0, crane_height), (0, 0, 1))
        )
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_wa.name}')
        md.landmarks[lm_name] = x, y, z
        lm_name = f"PTCC {lm_name[-3:]} (BB2)"
        z = crane_bb_height
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_wa.name}')
        md.landmarks[lm_name] = x, y, z

    print("\nDiner (W) (B)")
    ssb_height = 120.0
    lm_name = "Sunshine Skyway Bridge (N)"
    md.landmarks[lm_name] = ml.intersect_ray_and_plane(
        (cam_wa.xyz, cam_wa.get_landmark_direction(lm_name)),
        ((0, 0, ssb_height), (0, 0, 1))
    )
    cam_wb.calibrate_yaw_and_pitch(lm_name)
    print(cam_wb)

    print("\nDiner (NW)")
    og_pitch = cam_nw.pitch
    for pitch in np.arange(1.4, 2.21, 0.1):
        filename = f"triangulate/diner nw pitch={pitch:.3f}.png"
        if os.path.exists(filename): continue
        cam = ml.get_camera(cam_nw.name).open()
        cam.set_ypr((cam.yaw, pitch, cam.roll))
        cam.render_player().render_vertical_lines().render_distance_circles().render_camera_info()
        cam.save(filename)
    cam_nw.set_ypr((cam_nw.yaw, og_pitch, cam_nw.roll))
    cam_nw.test_lines()
    lm_names = [
        "536 Richard Jackson Blvd (RSE)",
        "536 Richard Jackson Blvd (RSW)",
        "Waffles Sign (TR)"
    ]
    best_loss = float("inf")
    best_deltas = None
    best_yaw = None
    for yaw in np.arange(16.0, 20.001, 0.001):
        cam_nw.set_ypr((yaw, cam_nw.pitch, cam_nw.roll))
        deltas = []
        loss = 0
        for lm_name in lm_names:
            delta = ml.intersect_ray_and_ray(
                (cam_wa.xyz, cam_wa.get_landmark_direction(lm_name)),
                (cam_nw.xyz, cam_nw.get_landmark_direction(lm_name))
            )[-1]
            deltas.append(delta)
            loss += delta ** 2
        loss /= len(lm_names)
        if loss < best_loss:
            best_loss = loss
            best_deltas = deltas
            best_yaw = yaw
    cam_nw.set_ypr((best_yaw, cam_nw.pitch, cam_nw.roll))
    print(cam_nw)
    for lm_name in lm_names:
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_wa.name, cam_nw.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_wa.name} & {cam_nw.name}')
        md.landmarks[lm_name] = x, y, z

    print("\nDiner (N)")
    cam_n.calibrate_yaw_and_pitch("536 Richard Jackson Blvd (RSE)")
    print(cam_n)
    lm_name = "536 Richard Jackson Blvd (RNE)"
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_nw.name, cam_n.name, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_nw.name} & {cam_n.name}')
    md.landmarks[lm_name] = x, y, z

    direction_w = ml.get_direction(
        md.landmarks["536 Richard Jackson Blvd (RSE)"],
        md.landmarks["536 Richard Jackson Blvd (RSW)"],
    )
    direction_n = ml.get_direction(
        md.landmarks["536 Richard Jackson Blvd (RSE)"],
        md.landmarks["536 Richard Jackson Blvd (RNE)"],
    )
    bearing_w = ml.get_angles_from_direction(direction_w)[0]
    bearing_n = ml.get_angles_from_direction(direction_n)[0]
    angle = bearing_w + 360 - bearing_n
    print(f"{angle=:.3f}")

    """
    lm_name = "Sunshine Skyway Bridge (N)"
    cam_c2 = ml.get_camera("Chase (2) (A)")
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_wa.name, cam_c2.name, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_wa.name} & {cam_c2.name}')
    """

    for cam_name, lm_name in (
        ("Hedge (B)", "Mount Mountain"),
        ("Gas Station (Lucia)", "Mount Waffles"),
        ("Gas Station (Lucia)", "Mount Waffles (TE)"),
        ("Gas Station (Lucia)", "Mount Waffles (TW)"),
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_n.name, cam_name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_n.name} & {cam_name}')

    print("\nDiner (NE)")
    cam_ne.calibrate_yaw_and_pitch("536 Richard Jackson Blvd (RSE)")
    print(cam_ne)
    target_height = 8.5
    lm_name_t, lm_name_b = "Train Tunnel (T)", "Train Tunnel (B)"
    dir_t = cam_ne.get_landmark_direction(lm_name_t)
    dir_b = cam_ne.get_landmark_direction(lm_name_b)
    d = 500
    while True:
        tunnel_t = ml.get_point(cam_ne.xyz, dir_t, d)
        tunnel_b = ml.intersect_ray_and_ray(
            (tunnel_t, (0, 0, -1)),
            (cam_ne.xyz, dir_b) 
        )[1]
        current_height = tunnel_t[2] - tunnel_b[2]
        if current_height >= target_height:
            print(f"{d=:.3f}")
            x, y, z = tunnel_t
            print(f'    "{lm_name_t}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_ne.name}')
            x, y, z = tunnel_b
            print(f'    "{lm_name_b}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_ne.name}')
            break
        d += 0.001
    for lm_name in ("Beige Billboard (BE)", "Waffles Billboard (BW)"):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_n.name, cam_ne.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_n.name} & {cam_ne.name}')
        md.landmarks[lm_name] = x, y, z

    print("\nDiner (E)")
    cam_e.calibrate_yaw_and_pitch("Waffles Billboard (BW)")
    print(cam_e)
    for lm_name in ("Domed Hills Sign (TW)", "Waffles Arrow", "Waffles Billboard", "White Pole"):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_ne.name, cam_e.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_ne.name} & {cam_e.name}')
        md.landmarks[lm_name] = x, y, z

    print("\nDiner (SE) (A)")
    cam_sea.calibrate_yaw_and_pitch("Domed Hills Sign (TW)")
    print(cam_sea)
    for lm_name in ("Traffic Sign",):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_e.name, cam_sea.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_e.name} & {cam_sea.name}')
        md.landmarks[lm_name] = x, y, z

    print("\nDiner (SE) (B)")
    cam_seb.calibrate_yaw_and_pitch("Traffic Sign")
    print(cam_seb)
    for lm_name in ("Easy Inn Sign",):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_sea.name, cam_seb.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_sea.name} & {cam_seb.name}')
        md.landmarks[lm_name] = x, y, z

    print("\nEasy Inn")
    cam_ei.calibrate_yaw_and_pitch("Easy Inn Sign")
    print(cam_ei)

    print("\nCar Wash")
    print(cam_cw)
    cam_cw.test_lines()
    cam_cw.test_player()
    cam_gsl = ml.get_camera("Gas Station (Lucia)")
    for lm_name in ("Springfield Community Church (CW)", "Pylon (3)"):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_cw.name, cam_gsl.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_cw.name} & {cam_gsl.name}')

    print("\nDiner (SW)")
    cam_sw.calibrate_yaw_and_pitch("Sunshine Skyway Bridge (N)")
    print(cam_sw)
    lm_name = "Water Tower (North Port Gellhorn)"
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_wa.name, cam_sw.name, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_wa.name} & {cam_sw.name}')

    m = ml.get_map("yanis").open(scale=2)
    m.draw_all()
    area = (-6500, 4250, -6000, 4750)
    m.save("triangulate/diner map.png", area)


if sys.argv[1] == "-gsl":

    aiwe_cam = ml.get_camera("AI World Editor Map (4K)")
    cam = ml.get_camera("Gas Station (Lucia)")
    cam.test_lines()
    lm_names = (
        "Coyote's (SE)",
        "1703 E 5th St (Warehouse) (NW)",
        "1703 E 5th St (Warehouse) (SW)",
        "4937 E Hwy 98 (Gas Station) (NE)",
        "6232 E Hwy 98 (SE)",
        "Large White Billboard",
        "Parker City Hall (SW)",
        "Parker Community Center (SW)",
        "Parker Police Station (SW)",
        "Port Gellhorn Smokestack",
        "Welcome to Port Gellhorn Sign"
    )
    yaw_values = [
        cam.calibrate_yaw(lm_name).yaw
        for lm_name in lm_names
    ]
    yaw_min = min(yaw_values)
    yaw_max = max(yaw_values)
    step = 0.001
    best_loss = float("inf")
    best_yaw = None
    for yaw in np.arange(yaw_min, yaw_max + step, step):
        cam.set_ypr((yaw, cam.pitch, cam.roll))
        loss = 0
        for lm_name in lm_names:
            loss += ml.intersect_ray_and_ray(
                (cam.xyz, cam.get_landmark_direction(lm_name)),
                (aiwe_cam.xyz, aiwe_cam.get_landmark_direction(lm_name))
            )[-1]
            if loss < best_loss:
                best_loss = loss
                best_yaw = cam.yaw

    cam.set_ypr((best_yaw, cam.pitch, cam.roll)).register()
    for lm_name in lm_names:
        m, (x, y, z), b, d, _ = ml.intersect_ray_and_ray(
            (cam.xyz, cam.get_landmark_direction(lm_name)),
            (aiwe_cam.xyz, aiwe_cam.get_landmark_direction(lm_name))
        )
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {aiwe_cam.name} & {cam.name}')
    print(cam)


if sys.argv[1] == "-gsj":

    cam = ml.get_camera("Gas Station (Jason)")
    cam.test_lines()
    cam = ml.find_camera(
        cam.name,
        [
            "4937 E Hwy 98 (Gas Station) (NE)",
            "Parker City Hall (SW)",
            "Port Gellhorn Smokestack",
            "Welcome to Port Gellhorn Sign",
        ],
        [
            ("AI World Editor Map (4K)", "4937 E Hwy 98 (Gas Station) (SE)"),
            # ("AI World Editor Map (4K)", "Mr. Bingo (SE)"),
            # ("Gas Station (Lucia)", "Mount Waffles (W)"),
        ],
        ((cam.x, cam.y), (cam.x, cam.y)), 0, 1,
        None, (cam.pitch, cam.pitch + 1, 1), (cam.hfov, cam.hfov + 1, 1),
        "yanis", 1, (cam.x - 500, cam.y - 500, cam.x + 500, cam.y + 500),
        None,
        "triangulate/gsj"
    )

    cam.register()
    aiwe_cam = ml.get_camera("AI World Editor Map (4K)")
    for lm_name in (
        "4937 E Hwy 98 (Gas Station) (SE)",
        "Port Gellhorn Smokestack"
    ):
        (x, y, z), a, b, d, _ = ml.find_landmark(aiwe_cam.name, cam.name, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {aiwe_cam.name} & {cam.name}')


if sys.argv[1] == "-mtw":

    cam_name_0 = "Gas Station (Lucia)"
    cam_name_1 = "Diner (N)"
    cam = ml.get_camera(cam_name_1)
    cam.test_lines()
    cam.test_player()
    lm_name = "Mount Waffles (TW)"
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')


if sys.argv[1] == "-chase2":

    """
    cam, loss = ml.find_camera(
        "Chase (2) (A)",
        [
            "Pylon (3)",
        ],
        [
            ("Gas Station (Lucia)", "Oval Yellow Sign"),
            ("Diner (W) (A)", "Sunshine Skyway Bridge (N)"),
            ("AI World Editor Map (4K)", "Wildfire Scooters (NW)"),
            ("AI World Editor Map (4K)", "Wildfire Scooters (S)"),
        ],
        ((-6480, 3278), (-6480, 3278)), 5, 0.1,
        (-5.0, 15.0), (1.5, 4.6, 0.1), (40, 60.1, 0.1),
        "yanis", 2, (-7000, 2750, -6000, 3750),
        None,
        "triangulate/chase2a"
    )
    # exit()
    """
    cam = ml.get_camera("Chase (2) (A)")
    lm_name_n, lm_name_s = "Sunshine Skyway Bridge (N)", "Sunshine Skyway Bridge (S)"
    height = md.landmarks[lm_name_n][2]
    x, y, z = ml.intersect_ray_and_plane(
        (cam.xyz, cam.get_landmark_direction(lm_name_s)),
        ((0, 0, height), (0, 0, 1))
    )
    print(f'    "{lm_name_s}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    cam = ml.get_camera("Diner (W) (A)")
    lm_name_nr = "Sunshine Skyway Bridge (NR)"
    x, y, z = ml.intersect_ray_and_ray(
        (md.landmarks[lm_name_n], (0, 0, -1)),
        (cam.xyz, cam.get_landmark_direction(lm_name_nr)),
    )[1]
    print(f'    "{lm_name_nr}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')

    ssb_n, ssb_s = md.landmarks[lm_name_n], md.landmarks[lm_name_s]
    ssb_nr = x, y, z
    lm_name_sr = "Sunshine Skyway Bridge (SR)"
    x, y, z = (ssb_s[0], ssb_s[1], ssb_nr[2])
    print(f'    "{lm_name_sr}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')

    dir_n = ml.get_direction(ssb_s, ssb_n)
    bearing_n = ml.get_angles_from_direction(dir_n)[0]
    bearing_w = bearing_n + 90
    dir_w = ml.get_direction_from_angles(bearing_w, 0)
    lm_name_nnr = "Sunshine Skyway Bridge (NNR)"
    x, y, z = ml.intersect_ray_and_plane(
        (cam.xyz, cam.get_landmark_direction(lm_name_nnr)),
        (ssb_n, dir_w)
    )
    print(f'    "{lm_name_nnr}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    ssb_nnr = x, y, z
    lm_name_ssr = "Sunshine Skyway Bridge (SSR)"
    dx = ssb_nr[0] - ssb_nnr[0]
    dy = ssb_nr[1] - ssb_nnr[1]
    x, y, z = (ssb_s[0] + dx, ssb_s[1] + dy, ssb_nnr[2])
    print(f'    "{lm_name_ssr}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    # exit()

    cam, loss = ml.find_camera(
        "Chase (2) (B)",
        [
            "Sunshine Skyway Bridge (N)",
            "Sunshine Skyway Bridge (S)",
        ],
        [
            ("AI World Editor Map (4K)", "Wildfire Scooters (NW)"),
            ("AI World Editor Map (4K)", "Wildfire Scooters (S)"),
            ("AI World Editor Map (4K)", "Wildfire Scooters (SE)"),
            ("AI World Editor Map (4K)", "Wildfire Scooters (W)"),
        ],
        ((-6473, 3247), (-6473, 3247)), 5, 0.1,
        (0.0, 10.0), (1.0, 4.6, 0.1), (48.0, 48.5, 0.1),
        "yanis", 2, (-7000, 2750, -6000, 3750),
        None,
        "triangulate/chase2b"
    )


if sys.argv[1] == "-pghp":

    crane_height = 74.5
    crane_bb_height = 40.5
    dc, ndc = (2, 3), 1
    """
    cam = ml.get_camera("Diner (W) (A)")
    for lm_name in (f"Port of Tampa Container Crane ({dc[0]})", f"Port of Tampa Container Crane ({dc[1]})"):
        x, y, z = ml.intersect_ray_and_plane(
            (cam.xyz, cam.get_landmark_direction(lm_name)),
            ((0, 0, crane_height), (0, 0, 1))
        )
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
        md.landmarks[lm_name] = x, y, z
        md.landmarks[f"{lm_name} (BB)"] = x, y, crane_bb_height
        print(f'    "{lm_name} (BB)": ({x:.3f}, {y:.3f}, {crane_bb_height:.3f}),  # via {cam.name}')
    exit()
    """

    """
    cam, loss = ml.find_camera(
        "Port Gellhorn Postcard (X)",
        [
            #"Port of Tampa Container Crane (1)",
            ##"Port of Tampa Container Crane (2)",
            ##"Port of Tampa Container Crane (2) (BB2)",
            "Port of Tampa Container Crane (3)",
            "PTCC (3) (BB2)",
        ],
        [
            ("Chase (2) (A)", "Juice Fruit Sign"),
            ("Chase (2) (A)", "Juice Fruit Sign (B)"),
            ("Chase (2) (A)", "Juice Fruit Sign (E)"),
            ("Chase (2) (A)", "Juice Fruit Sign (W)"),
            ##("Chase (2) (A)", "New Foundation Church"),
            #("Port Gellhorn 04 (Delights) (X)", "Train Signal (S) (E)"),
            #("Port Gellhorn 04 (Delights) (X)", "Train Signal (S) (W)"),
            #("Port Gellhorn 04 (Delights) (X)", "Water Tower (West Port Gellhorn) (C)"),
        ],
        ((-6540+15, 3550-60), (-6540-15, 3550+60)), 10, 1.0,
        #((-6560+16, 3600-50), (-6560-16, 3600+50)), 10, 1.0,
        (10, 40), (-4.0, 0.1, 0.1), (55, 85.1, 0.5),
        "yanis", 2, (-7250, 3250, -6250, 4250),
        None, # md.map_sections["Port Gellhorn"],
        "triangulate/pghp"
    )
    exit()
    """
    cam = ml.get_camera("Port Gellhorn Postcard (X)")
    m = ml.get_map("yanis")
    lm_names = (f"Port of Tampa Container Crane ({ndc})", "Port of Tampa Container Crane (2)")
    for lm_name in lm_names:
        x, y, z = ml.intersect_ray_and_plane(
            (cam.xyz, cam.get_landmark_direction(lm_name)),
            ((0, 0, crane_height), (0, 0, 1))
        )
        md.landmarks[lm_name] = x, y, z
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
    lm_names = [lm_name for lm_name in cam.landmark_pixels if "Canal" in lm_name or "Island" in lm_name or "Ship" in lm_name]
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
        md.landmarks[lm_name] = x, y, z
        letter = ml.get_letter(lm_name)
        m.draw_circle(md.landmarks[lm_name], 5, fill=(0, 192, 0), outline=(255, 255, 255), width=1, text=letter)    
    lm_names = sorted([lm_name for lm_name in cam.landmark_pixels if lm_name.startswith("Bay ")])
    for lm_name in lm_names:
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')
        md.landmarks[lm_name] = x, y, z
    cam_w = ml.get_camera("Diner (W) (A)")
    lm_names = sorted([lm_name for lm_name in cam_w.landmark_pixels if lm_name.startswith("Bay ")])
    for lm_name in lm_names:
        x, y, z = cam_w.get_point_at_zero_elevation(cam_w.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_w.name}')
        md.landmarks[lm_name] = x, y, z
    cam_sw = ml.get_camera("Diner (SW)")
    lm_names = sorted([lm_name for lm_name in cam_sw.landmark_pixels if lm_name.startswith("Bay ")])
    for lm_name in lm_names:
        x, y, z = cam_sw.get_point_at_zero_elevation(cam_sw.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_sw.name}')
        md.landmarks[lm_name] = x, y, z
    m.draw_line(
        (md.landmarks[f"Bay (AAA)"], md.landmarks[f"Bay (BBB)"]),
        fill=(0, 0, 192), width=1
    )
    m.draw_circle(md.landmarks[f"Bay (AAA)"], 5, fill=(0, 0, 192), outline=(255, 255, 255), width=1, text="A")      
    m.draw_circle(md.landmarks[f"Bay (BBB)"], 5, fill=(0, 0, 192), outline=(255, 255, 255), width=1, text="B")      
    letters = "ABCDEFG"
    for i, letter in enumerate(letters):
        if letter not in "CEG":
            m.draw_line(
                (md.landmarks[f"Bay ({letter}{letter})"], md.landmarks[f"Bay ({letters[i + 1]}{letters[i + 1]})"]),
                fill=(192, 0, 0), width=1
            )
    for letter in letters:
        m.draw_circle(md.landmarks[f"Bay ({letter}{letter})"], 5, fill=(192, 0, 0), outline=(255, 255, 255), width=1, text=letter)      
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, letter in enumerate(letters):
        if letter not in "FHMOQSWZ":
            m.draw_line(
                (md.landmarks[f"Bay ({letter})"], md.landmarks[f"Bay ({letters[i + 1]})"]),
                fill=(0, 192, 0), width=1
            )
    for letter in letters:
        m.draw_circle(md.landmarks[f"Bay ({letter})"], 5, fill=(0, 192, 0), outline=(255, 255, 255), width=1, text=letter)        
    for lm_name in (
            "Port of Tampa Container Crane (1)",
            "Port of Tampa Container Crane (2)",
            "Port of Tampa Container Crane (3)",
            "Sunshine Skyway Bridge (N)",
            "Sunshine Skyway Bridge (S)"
        ):
        color = ml.get_color(lm_name)
        letter = ml.get_letter(lm_name)
        m.draw_circle(md.landmarks[lm_name], 10, fill=color, outline=(255, 255, 255), width=1, text=letter)        
    m.save("triangulate/pghp map coastline.png", md.map_sections["Port Gellhorn"])    

    cam = ml.get_camera("Diner (W) (A)")
    cam.render_all().save("triangulate/pghp diner wa.png")

    lm_name = "Mount Waffles (TW)"
    cam_xyz = md.landmarks[lm_name]
    cam = ml.Camera(
        "X/0", "Mount Waffles", None,
        cam_xyz, (135, -10, 0), (60, None),
        (1920, 1080), ""
    )
    cam.open(scale=1)
    cam.project_map("yanis", opacity=0.75, keep_rgb=True)
    cam.render_vanishing_points()
    cam.render_distance_circles()
    cam.render_cameras()
    cam.render_rays()
    cam.render_landmarks()
    cam.render_pixels()
    for lm_name, cam_names in (
        ("Sunshine Skyway Bridge (N)", ["Diner (W) (A)", "Chase (2) (A)"]),
        ("Sunshine Skyway Bridge (S)", ["Chase (2) (A)"]),
        ("Port of Tampa Container Crane (1)", ["Port Gellhorn Postcard (X)"]),
        ("Port of Tampa Container Crane (2)", ["Diner (W) (A)", "Port Gellhorn Postcard (X)"]),
        ("Port of Tampa Container Crane (3)", ["Diner (W) (A)", "Port Gellhorn Postcard (X)"]),
        ("Pylon (3)", ["Gas Station (Lucia)", "Car Wash", "Chase (1)", "Chase (2) (A)"]),
        ("Oval Yellow Sign", ["Gas Station (Lucia)", "Chase (2) (A)"]),
        ("Juice Fruit Sign (B)", ["Chase (2) (A)", "Port Gellhorn Postcard (X)", "Port Gellhorn 04 (Delights) (X)"]),
        ("New Foundation Church", ["Chase (2) (A)", "Port Gellhorn Postcard (X)"]),
        ("Train Signal (S) (W)", ["Port Gellhorn Postcard (X)", "Port Gellhorn 04 (Delights) (X)"]),
        ("Water Tower (West Port Gellhorn) (C)", ["Port Gellhorn Postcard (X)", "Port Gellhorn 04 (Delights) (X)"]),
        ("Wildfire Scooters (NW)", ["AI World Editor Map (4K)", "Chase (2) (A)"]),
        ("Wildfire Scooters (S)", ["AI World Editor Map (4K)", "Chase (2) (A)"]),
    ):
        cam.render_box(md.landmarks[lm_name], (1, 1, 1), 0, ml.get_color(lm_name), 1)
        for cam_name in cam_names:
            lm_cam = ml.get_camera(cam_name)
            cam.render_line((lm_cam.xyz, md.landmarks[lm_name]), ml.get_color(lm_name), 1)
    cam.render_camera_info()
    cam.save("triangulate/pghp mount waffles sw.png")


if sys.argv[1] == "-delights":

    """
    cam, loss = ml.find_camera(
        "Port Gellhorn 04 (Delights) (X)",
        [
            "Juice Fruit Sign (B)"
        ],
        [
            ("Port Gellhorn Postcard (X)", "Train Signal (S) (E)"),
            ("Port Gellhorn Postcard (X)", "Train Signal (S) (W)"),
            ("Port Gellhorn Postcard (X)", "Water Tower (West Port Gellhorn) (C)"),
        ],
        #((-6320, 3690), (-6320, 3690)), 50, 1,
        ((-6337, 3617), (-6348, 3730)), 5, 1,
        (7, 15), (-24.0, -15.9, 0.1), (65, 85.1, 0.1),
        "yanis", 1, (-6750, 3250, -5750, 4250),
        None,
        "triangulate/delights"
    )
    exit()
    """
    cam = ml.get_camera("Port Gellhorn 04 (Delights) (X)")
    cam_pghp = ml.get_camera("Port Gellhorn Postcard (X)")
    lm_name = "Water Tower (West Port Gellhorn)"
    lm_name_c = "Water Tower (West Port Gellhorn) (C)"
    p, a, (x, y, z), d, _ = ml.intersect_ray_and_ray(
        (cam_pghp.xyz, cam_pghp.get_landmark_direction(lm_name)),
        (md.landmarks[lm_name_c], (0, 0, 1))
    )
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_pghp.name} & {cam.name}')


if sys.argv[1] == "-mountainpass":
    cam = ml.get_camera("Mount Kalaga National Park 04 (Mountain Pass) (X)")
    cam, loss = ml.find_camera(
        "Mount Kalaga National Park 04 (Mountain Pass) (X)",
        [
            "Water Tower near Prison",
        ],
        [
            ("Gas Station (Lucia)", "Billboard (Delights)"),
            ("Diner (SE) (A)", "Quarry"),
        ],x
        ((-5000, 5300), (-5000, 5300)), 150, 1,
        (75, 125), (-15.0, -9.9, 0.1), (45.0, 90.1, 0.1),
        "yanis", 1, (-7000, 2000, -4000, 6000),
        None, # md.map_sections["Port Gellhorn"],
        "triangulate/mountainpass"
    )

if sys.argv[1] == "-mountain_helicopter":

    elevation = {
        "Ambrosia Hill (A)": 165,
        "Ambrosia Hill (B)": 130,
        "Ambrosia Road (A)": 15,
        "Ambrosia Road (B)": 25,
        "Ambrosia Road (C)": 30,
        "Canal (A)": 5,
        "Canal (B)": 5,
        "Canal (C)": 10,
        "Canal (D)": 15,
        "Canal Road (A)": 10,
        "Canal Road (B)": 10,
        "I-404 (A)": 50,
        "I-404 (B)": 50,
        "I-404 (C)": 50,
        "Kissimmee River (A)": 5,
        "Kissimmee River (B)": 5,
        "Mount Leonida (A)": 250,
        "Mount Leonida (B)": 180,
        "Offramp (N) (A)": 40,
        "Offramp (N) (B)": 40,
        "Offramp (N) (C)": 35,
        "Offramp (S) (A)": 35,
        "Offramp (S) (B)": 30,
        "Ramp": 15,
        "Road (A)": 10,
        "Road (B)": 25,
        "Route 50 (A)": 15,
        "Route 50 (B)": 15,
        "Route 50 (C)": 15,
        "Route 50 (D)": 25,
        "Route 50 (E)": 35,
        "Starlet Highway (A)": 60,
        "Starlet Highway (B)": 40,
        "Starlet Highway (C)": 20,
    }
    pairs = [
        ("Ambrosia Hill (A)", "Ambrosia Hill (B)"),
        ("Ambrosia Road (A)", "Ambrosia Road (B)"),
        ("Ambrosia Road (B)", "Ambrosia Road (C)"),
        ("Ambrosia Road (A)", "Route 50 (B)"),
        ("Canal (A)", "Canal (B)"),
        ("Canal (B)", "Canal (C)"),
        ("Canal (C)", "Canal (D)"),
        ("Canal Road (A)", "Canal Road (B)"),
        ("I-404 (A)", "I-404 (B)"),
        ("I-404 (B)", "I-404 (C)"),
        ("Kissimmee River (A)", "Kissimmee River (B)"),
        ("Mount Leonida (A)", "Mount Leonida (B)"),
        ("Offramp (N) (A)", "Offramp (N) (B)"),
        ("Offramp (N) (B)", "Offramp (N) (C)"),
        ("Offramp (S) (A)", "Offramp (S) (B)"),
        ("Ramp", "Route 50 (D)"),
        ("Road (A)", "Road (B)"),
        ("Route 50 (A)", "Route 50 (B)"),
        ("Route 50 (B)", "Route 50 (C)"),
        ("Route 50 (C)", "Route 50 (D)"),
        ("Route 50 (D)", "Route 50 (E)"),
        ("Starlet Highway (A)", "Starlet Highway (B)"),
        ("Starlet Highway (B)", "Starlet Highway (C)"),
    ]
    cam = ml.get_camera("Mount Kalaga National Park 02 (Helicopter) (X)")
    cam_diner = ml.get_camera("Diner (NE)").render_all()
    cam_hedge = ml.get_camera("Hedge (B)").render_all()
    m = ml.get_map("yanis")
    for lm_name_a, lm_name_b in pairs:
        z_a, z_b = elevation[lm_name_a], elevation[lm_name_b]
        dir_a, dir_b = cam.get_landmark_direction(lm_name_a), cam.get_landmark_direction(lm_name_b)
        point_a = ml.intersect_ray_and_plane((cam.xyz, dir_a), (z_a, (0, 0, 1)))
        point_b = ml.intersect_ray_and_plane((cam.xyz, dir_b), (z_b, (0, 0, 1)))
        color = ml.get_color(lm_name_a)
        cam.render_line((point_a, point_b), color, 5)
        cam_diner.render_line((point_a, point_b), color, 5)
        cam_hedge.render_line((point_a, point_b), color, 5)
        steps = int(round(np.linalg.norm(point_a - point_b)))
        for i in range(steps):
            t = i / steps
            point = (1 - t) * point_a + t * point_b
            m.draw_circle(point, 5, color, (255, 255, 255), 0)
    for lm_name, z in elevation.items():
        direction = cam.get_landmark_direction(lm_name)
        point = ml.intersect_ray_and_plane((cam.xyz, direction), (z, (0, 0, 1)))
        color = ml.get_color(lm_name)
        letter = ml.get_letter(lm_name)
        m.draw_circle(point, 10, color, (255, 255, 255), 1, letter)
    m.save("triangulate/mountain_helicopter map.png", (-7500, 500, -1500, 6500))
    cam.render_all().save("triangulate/mountain_helicopter cam.png")
    cam_diner.save("triangulate/mountain_helicopter cam diner.png")
    cam_hedge.save("triangulate/mountain_helicopter cam hedge.png")
    exit()

    filename = "triangulate/mountain_helicopter.png"
    if not os.path.exists(filename):
        area = (-7500, 500, -1500, 6500)
        m = ml.get_map("yanis")
        cam_name = "Mount Kalaga National Park 02 (Helicopter) (X)"
        m.project_camera_parallel(cam_name, area=area, r=(0, 12000))
        m.save(filename, area)


### AMBROSIA

if sys.argv[1] == "-ambrosia_bikers":
    point_c = md.landmarks["Ambrosia Main St (C)"][:2]
    point_d = md.landmarks["Ambrosia Main St (D)"][:2]
    point_e = (point_d[0] + point_d[0] - point_c[0], point_d[1] + point_d[1] - point_c[1])
    cam, loss = ml.find_camera(
        "Ambrosia 01 (Bikers)",
        [
            "Billboard with Irregular Shape",
            "Billboard with Oval Motif #1",
        ],
        [
            ("Ambrosia 02 (Panorama)", "Large Billboard (Ambrosia)")
        ],
        (point_d, point_e), 25, 1,
        (4.9, 5.1), (-1.5, 0.6, 0.1), (40.0, 60.1, 0.1),
        "yanis", 1, (-4000, 3000, -2000, 5000),
        None,
        "triangulate/ambrosia_bikers"
    )


if sys.argv[1] == "-ambrosia":

    fake_cam_name = "WDNA FM Fake Cam"
    md.cameras[fake_cam_name] = {
        "id": "X",
        "player": None,
        "xyz": md.landmarks["WDNA FM"],
        "ypr": (0, -89.999, 0),
        "fov": (90, None),
        "size": (3840, 2160),
        "source": ""
    }
    md.pixels[fake_cam_name] = {
        "WDNA FM (B)": (1920, 1080)
    }

    hfov_range = (52.0, 55.1, 0.5)

    for hfov in np.arange(*hfov_range):
        json_filename = f"triangulate/ambrosia panorama {hfov=:.3f}.json"
        if os.path.exists(json_filename): continue
        cam, loss = ml.find_camera(
            "Ambrosia 02 (Panorama)",
            [
                "FAA Miami ATCT (MIA)"
            ],
            [
                ("Leonida Keys 01 (Airplane) (X)", "MIA North Terminal Tower"),
                ("Loading Zone near Prison (SW)", "Water Tower near Prison"),
                ("WDNA FM Fake Cam", "WDNA FM (B)"),
                # ("Leonida Keys 01 (Airplane) (X)", "Wheelabrator South Broward"),
                # ("Leonida Keys 01 (Airplane) (X)", "Wheelabrator South Broward (W)"),
            ],
            ((-2465, 4500), (-2465, 6000)), 25, 1,
            (50, 80), (-4.5, -2.5, 0.1), (hfov, hfov + 0.1, 1.0),
            "yanis", 1, (-4000, 2000, -500, 7000),
            None, # (-4000, 3000, -1000, 7000),
            json_filename.replace(".json", "")
        )
        with open(json_filename, "w") as f:
            json.dump({
                "loss": loss,
                "xyz": list(float(v) for v in cam.xyz),
                "ypr": list(float(v) for v in cam.ypr),
                "fov": list(float(v) for v in cam.fov),
            }, f, indent=4)

    filename = "triangulate/ambrosia lake leonida.png"
    if not os.path.exists(filename):
        m = ml.get_map("yanis")
        for i, hfov in enumerate(np.arange(*hfov_range)):
            #filename = f"triangulate/ambrosia lake leonida {hfov=:.3f}.png"
            #if os.path.exists(filename): continue
            json_filename = f"triangulate/ambrosia panorama {hfov=:.3f}.json"
            with open(json_filename) as f:
                data = json.load(f)
            cam = ml.get_camera("Ambrosia 02 (Panorama)")
            cam.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
            m.draw_camera(cam)
            color = ml.get_rgb(i * 360 / len(list(np.arange(*hfov_range))), 1.0, 0.75)
            m.draw_circle(cam.xyz, 12, color, (255, 255, 255), 1, f"{i + 1}")
            points = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWX":
                point = ml.intersect_ray_and_plane(
                    (cam.xyz, cam.get_landmark_direction(f"Lake Leonida ({letter})")),
                    ((0, 0, 5), (0, 0, 1))
                )[:2]
                points.append(point)
                if len(points) > 1:
                    m.draw_line((points[-2], points[-1]), color, 2)
                m.draw_circle(point, 6, color, (255, 255, 255), 1, letter)
        m.save(filename, (-4000, 2000, -500, 7000))

    panorama_data = {}
    for hfov in np.arange(*hfov_range):
        json_filename = f"triangulate/ambrosia panorama {hfov=:.3f}.json"
        with open(json_filename) as f:
            data = json.load(f)
        panorama_data[hfov] = data
        cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
        cam_panorama.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
        x, y, z = {}, {}, {}
        for i, lm_name in enumerate((
            "Wheelabrator South Broward",
            "Wheelabrator South Broward (W)"
        )):
            idx = 1
            md.landmarks[lm_name] = ml.find_landmark(
                "Ambrosia 02 (Panorama)",
                "Leonida Keys 01 (Airplane) (X)",
                lm_name
            )[idx]
            x[i], y[i], z[i] = md.landmarks[lm_name]
        print(
            f"{hfov=:.1f} loss={data['loss']:.6f} z={data['xyz'][2]:.3f} pitch={data['ypr'][1]:.3f} "
            f"brator=(({x[0]:.3f}, {y[0]:.3f}, {z[0]:.3f}), ({x[1]:.3f}, {y[1]:.3f}, {z[1]:.3f}))"
        )

    max_size_delta=1.2
    rays = [
        ("Ambrosia 02 (Panorama)", "Sebring Water Tower"),
        ("Ambrosia 02 (Panorama)", "Sebring Water Tower (B)"),
        ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Tank)"),
        ("Ambrosia 02 (Panorama)", "US Sugar Mill (Factory)"),
        ("Ambrosia 02 (Panorama)", "US Sugar Mill (Factory) (R)"),
        ("Ambrosia 02 (Panorama)", "USSM Smokestack (4)"),
        ("Ambrosia 02 (Panorama)", "USSM Smokestack (5)"),
        ("Ambrosia 02 (Panorama)", "USSM Smokestack (6)"),
        ("Ambrosia 02 (Panorama)", "USSM Smokestack (7)"),
        ("Ambrosia 02 (Panorama)", "USSM Smokestack (8)"),
        ("Ambrosia 02 (Panorama)", "USSM Smokestack (9)"),
        ("Ambrosia 02 (Panorama)", "Wheelabrator South Broward (3B)"),
    ]
    for pass_ in (1,):
        for hfov in np.arange(*hfov_range):
            json_filename = f"triangulate/ambrosia panorama {hfov=:.3f}.json"
            with open(json_filename) as f:
                data = json.load(f)
            json_filename = f"triangulate/ambrosia panorama {hfov=:.3f} fires {pass_=}.json"
            if not os.path.exists(json_filename):
                cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
                cam_panorama.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
                lm_name = "Wheelabrator South Broward (W)"
                md.landmarks[lm_name] = ml.find_landmark(
                    "Ambrosia 02 (Panorama)",
                    "Leonida Keys 01 (Airplane) (X)",
                    lm_name
                )[1]
                brator_z = md.landmarks[lm_name][2]
                xy_center = {1: (-1400, 3250)}[pass_]
                xy_radius = {1: 350}[pass_]
                xy_step = {1: 10}[pass_]
                ml.get_camera("Ambrosia 04 (Fires)").clear_landmark_directions()  # needed?
                cam_fires, loss = ml.find_camera(
                    "Ambrosia 04 (Fires)",
                    [
                        "Sunshine Skyway Bridge (N)",
                        "Sunshine Skyway Bridge (S)",
                        # "Wheelabrator South Broward (W)",
                    ],
                    rays,
                    (xy_center, xy_center), xy_radius, xy_step,
                    (brator_z, brator_z + 20), (-3.0, -0.9, 0.1), (45.0, 70.1, 0.1),
                    "yanis", 1, (-4500, 2000, -500, 7000),
                    None,
                    json_filename.replace(".json", ""),
                    # bearing_limits=(89.0, 91.0, 2805),
                    ray_pairs=[
                        ("Ambrosia 02 (Panorama)", "Sebring Water Tower", "Sebring Water Tower (B)"),
                        ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Tank) (L)", "1500 Sonora Ave (Tank) (R)"),
                        ("Ambrosia 02 (Panorama)", "US Sugar Mill (Factory)", "US Sugar Mill (Factory) (R)"),
                        ("Ambrosia 02 (Panorama)", "Wheelabrator South Broward (W)", "Wheelabrator South Broward (3B)"),
                    ],
                    max_size_delta=max_size_delta
                )
                with open(json_filename, "w") as f:
                    json.dump({
                        "loss": loss,
                        "xyz": list(float(v) for v in cam_fires.xyz),
                        "ypr": list(float(v) for v in cam_fires.ypr),
                        "fov": list(float(v) for v in cam_fires.fov),
                    }, f, indent=4)
            else:
                with open(json_filename) as f:
                    data = json.load(f)
                cam_fires = ml.get_camera("Ambrosia 04 (Fires)")
                cam_fires.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()

            json_filename = f"triangulate/ambrosia panorama {hfov=:.3f} postcard {pass_=}.json"
            if not os.path.exists(json_filename):
                for cam_name, lm_name in rays:
                    md.landmarks[lm_name] = ml.find_landmark(
                        cam_fires.name, cam_name, lm_name
                    )[0]
                ray_a = (
                    (cam_panorama.x, cam_panorama.y, 0),
                    ml.get_direction_from_angles(
                        ml.get_angles_from_direction(
                            cam_panorama.get_landmark_direction("1500 Sonora Ave (Silo)")
                        )[0],
                        0.0
                    )
                )
                ray_b = (
                    (cam_fires.x, cam_fires.y, 0),
                    ml.get_direction_from_angles(cam_fires.yaw - cam_fires.hfov / 2, 0.0)
                )
                point = ml.intersect_ray_and_ray(ray_a, ray_b)[0]
                direction = ml.get_direction(point, cam_panorama.xyz)
                point_a = ml.get_point(point, direction, 150)[:2]
                point_b = ml.get_point(point, direction, 350)[:2]
                ml.get_camera("Ambrosia Postcard (X)").clear_landmark_directions()  # needed?
                cam_postcard, loss = ml.find_camera(
                    "Ambrosia Postcard (X)",
                    [
                        "Sebring Water Tower",
                        "Sebring Water Tower (B)",
                        "1500 Sonora Ave (Tank)",
                        "US Sugar Mill (Factory)",
                        "US Sugar Mill (Factory) (R)",
                        "USSM Smokestack (4)",
                        "USSM Smokestack (5)",
                        "USSM Smokestack (6)",
                        "USSM Smokestack (7)",
                        "USSM Smokestack (8)",
                        "USSM Smokestack (9)",
                    ],
                    [
                        ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Silo)"),
                        ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Silo) (N)"),
                        ("Ambrosia 02 (Panorama)", "USSM Smokestack (1)"),
                        ("Ambrosia 02 (Panorama)", "USSM Smokestack (2)"),
                        ("Ambrosia 04 (Fires)", "USSM Smokestack (3)"),
                        ("Ambrosia 02 (Panorama)", "USSM Smokestack (10)"),
                        ("Ambrosia 02 (Panorama)", "USSM Smokestack (11)"),
                    ],
                    (point_a, point_b), 150, 10,
                    (30, 60), (-2.0, 0.1, 0.2), (40.0, 70.1, 0.5),
                    "yanis", 1, (-3500, 2500, -1500, 4500),
                    None,
                    json_filename.replace(".json", ""),
                    ray_pairs=[
                        ("Ambrosia 02 (Panorama)", "Sebring Water Tower", "Sebring Water Tower (B)"),
                        ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Silo) (L)", "1500 Sonora Ave (Silo) (R)"),
                        ("Ambrosia 02 (Panorama)", "1500 Sonora Ave (Tank) (L)", "1500 Sonora Ave (Tank) (R)"),
                        ("Ambrosia 02 (Panorama)", "US Sugar Mill (Factory)", "US Sugar Mill (Factory) (R)"),
                    ],
                    max_size_delta=max_size_delta
                )
                with open(json_filename, "w") as f:
                    json.dump({
                        "loss": loss,
                        "xyz": list(float(v) for v in cam_postcard.xyz),
                        "ypr": list(float(v) for v in cam_postcard.ypr),
                        "fov": list(float(v) for v in cam_postcard.fov),
                    }, f, indent=4)

    for pass_ in (1,):
        filename = f"triangulate/ambrosia map {pass_=}.png"
        if not os.path.exists(filename):
            m = ml.get_map("yanis")
            for i, hfov in enumerate(np.arange(*hfov_range)):
                # fov_color = ml.get_rgb((hfov - 40) / 21 * 360, v=0.75)
                fov_color = ml.get_rgb(i * 360 / len(list(np.arange(*hfov_range))), 1.0, 0.75)
                json_filename = f"triangulate/ambrosia panorama {hfov=:.3f}.json"
                with open(json_filename) as f:
                    data = json.load(f)
                cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
                cam_panorama.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
                json_filename = f"triangulate/ambrosia panorama {hfov=:.3f} fires {pass_=}.json"
                with open(json_filename) as f:
                    data = json.load(f)
                cam_fires = ml.get_camera("Ambrosia 04 (Fires)")
                cam_fires.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
                json_filename = f"triangulate/ambrosia panorama {hfov=:.3f} postcard {pass_=}.json"
                with open(json_filename) as f:
                    data = json.load(f)
                cam_postcard = ml.get_camera("Ambrosia Postcard (X)")
                cam_postcard.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
                for cam in (cam_panorama, cam_fires, cam_postcard):
                    letter = ml.get_letter(cam.name)
                    m.draw_circle(cam.xy, 10, (255, 255, 255), fov_color, 1, letter)
                for cam_name_a, cam_name_b, lm_name in (
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "Sebring Water Tower"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia Postcard (X)", "1500 Sonora Ave (Silo)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "1500 Sonora Ave (Tank)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "US Sugar Mill (Factory)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia Postcard (X)", "USSM Smokestack (1)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia Postcard (X)", "USSM Smokestack (2)"),
                    ("Ambrosia 04 (Fires)", "Ambrosia Postcard (X)", "USSM Smokestack (3)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "USSM Smokestack (4)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "USSM Smokestack (5)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "USSM Smokestack (6)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "USSM Smokestack (7)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "USSM Smokestack (8)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia 04 (Fires)", "USSM Smokestack (9)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia Postcard (X)", "USSM Smokestack (10)"),
                    ("Ambrosia 02 (Panorama)", "Ambrosia Postcard (X)", "USSM Smokestack (11)"),
                    ("Leonida Keys 01 (Airplane) (X)", "Ambrosia 02 (Panorama)", "Wheelabrator South Broward"),
                    ("Leonida Keys 01 (Airplane) (X)", "Ambrosia 02 (Panorama)", "Wheelabrator South Broward (W)"),
                ):
                    cam_a = ml.get_camera(cam_name_a)
                    cam_b = ml.get_camera(cam_name_b)
                    point = ml.intersect_ray_and_ray(
                        (cam_a.xyz, cam_a.get_landmark_direction(lm_name)),
                        (cam_b.xyz, cam_b.get_landmark_direction(lm_name)),
                    )[0][:2]
                    r = 5 if "Smokestack" in lm_name else 10
                    letter = ml.get_letter(lm_name)
                    outline = (0, 0, 0) if cam_name_b == "Ambrosia Postcard (X)" else (255, 255, 255)
                    m.draw_circle(point, r, fov_color, outline, 1, letter)
                points = []
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWX":
                    point = ml.intersect_ray_and_plane(
                        (cam_panorama.xyz, cam_panorama.get_landmark_direction(f"Lake Leonida ({letter})")),
                        ((0, 0, 5), (0, 0, 1))
                    )[:2]
                    points.append(point)
                    if len(points) > 1:
                        m.draw_line(points[-2:], fov_color, 2)
                    m.draw_circle(point, 5, fov_color, (255, 255, 255), 1, letter)
                points = []
                for letter in "ABCD":
                    point = ml.intersect_ray_and_plane(
                        (cam_panorama.xyz, cam_panorama.get_landmark_direction(f"Main St ({letter})")),
                        ((0, 0, 10), (0, 0, 1))
                    )[:2]
                    points.append(point)
                    if len(points) > 1:
                        m.draw_line(points[-2:], fov_color, 2)
                    m.draw_circle(point, 5, fov_color, (255, 255, 255), 1, letter)
                for obj in ("Canal", "Car", "Path", "Road"):
                    for letter in "ABC":
                        points = []
                        for end in (1, 2):
                            point = ml.intersect_ray_and_plane(
                                (cam_fires.xyz, cam_fires.get_landmark_direction(f"{obj} {letter} ({end})")),
                                ((0, 0, 10), (0, 0, 1))
                            )[:2]
                            points.append(point)
                        m.draw_line(points, fov_color, 2)
                        for point in points:
                            m.draw_circle(point, 5, fov_color, (255, 255, 255), 1, letter)
                point = ml.intersect_ray_and_plane(
                    (cam_fires.xyz, cam_fires.get_landmark_direction(f"Radio Tower (Ambrosia) (B)")),
                    ((0, 0, 10), (0, 0, 1))
                )[:2]
                m.draw_circle(point, 10, fov_color, (255, 255, 255), 1, "B")
            m.save(filename, (-7500, 2000, -500, 7000))


### GLITCH

if sys.argv[1] == "-glitch_a":

    cam_name_a, cam_name_b = ("Glitch (A)", "Highway (NE)")
    lm_names = ("112 NE 41st St", "112 NE 41st St (SW)")
    cam = ml.get_camera(cam_name_a)
    pitch = -14.5
    for step in (1, -0.1, 0.01, -0.001):
        best_loss = float("inf")
        while True:
            cam.set_ypr((cam.yaw, pitch, cam.roll))
            loss = 0
            for lm_name in lm_names:
                delta = ml.find_landmark(cam_name_a, cam_name_b, lm_name)[-1]
                loss += delta ** 2
            loss /= 2
            if loss < best_loss:
                best_loss = loss
            else:
                break
            pitch += step
    pitch += 0.001
    cam.set_ypr((cam.yaw, pitch, cam.roll)).register()
    print(cam)
    for lm_name in lm_names:
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_a, cam_name_b, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_a} & {cam_name_b}')
    cam_name_c = "Tennis Court (NE)"
    for lm_name in ("112 NE 41st St (NW)", "112 NE 41st St (SE)"):
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_b, cam_name_c, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_b} & {cam_name_c}')
    for lm_name in (
        "East Coast (A)", "East Coast (B)", "East Coast (C)", "East Coast (D)",
        "East Coast (E)", "East Coast (F)", "East Coast (G)", "East Coast (H)",
        "East Coast (I)",
        "Golf Course (E)", "Golf Course (W)",
        "Lake (E)", "Lake (W)",
        "Park (E)", "Park (W)",
    ):
        x, y, z = cam.get_point_at_zero_elevation(cam.landmark_pixels[lm_name])
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam.name}')

    filename = "triangulate/glitch_a projection.png"
    if not os.path.exists(filename):
        area = (-4000, 1000, 3000, 12000)
        m = ml.get_map("yanis")
        m.project_camera_parallel(cam_name_a, area=area, r=(0, 12000))
        m.save(filename, area)


if sys.argv[1] == "-hedge_b":

    cam_name_0 = "Hedge (B)"
    cam_name_1 = "Diner (N)"
    lm_name = "Mount Mountain"
    (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')



if sys.argv[1] == "-grassrivers_postcard":

    cam_name_0, cam_name_1 = "Key Lento", "Grassrivers Postcard (X)"
    for lm_name in [
        "Naval Air Station Key West (Control Tower)",
        "Naval Air Station Key West (Radar Tower)",
    ]:
        (x, y, z), a, b, d, _ = ml.find_landmark(cam_name_0, cam_name_1, lm_name)
        print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # {d=:.3f} via {cam_name_0} & {cam_name_1}')
    exit()

    m = ml.get_map("yanis")
    cam_names = ("Leonida Keys 01 (Airplane) (X)", "Grassrivers Postcard (X)")
    area = (-8500, -8000, -2500, -2000)
    m.project_camera_parallel(cam_names, area=area, r=(0, 16000))
    m.save("triangulate/grassrivers_postcard_projection.png", crop=area)

