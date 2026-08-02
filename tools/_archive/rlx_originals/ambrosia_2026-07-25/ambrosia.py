import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

from gtamaplib import gtamaplib as ml
from gtamaplib import gtamapdata as md
from gtamaplib import gtamaputils as mu


dirname = "ambrosia"
os.makedirs(dirname, exist_ok=True)
map_area=(-5000, 2000, -500, 6500)

panorama_hfov_range = [50.0, 50.5, 51.0, 51.5, 49.5, 49.0, 47.5, 47.0, 48.5] + list(np.arange(48.0, 51.51, 0.5))
postcard_hfov_delta_range = [0.5, 0.0, -0.5, 1.0] + list(np.arange(-1.0, 1.51, 0.5))

if len(sys.argv) > 1 and sys.argv[1] == "--highres":
    panorama_hfov_range = np.arange(50.5, 51.01, 0.1)
    postcard_hfov_delta_range = [1.3] + list(np.arange(0.9, 1.41, 0.1))

silo_height = 44.3
silo_ratio = 3.2

def get_elevation(cam, lm_names, size, orientation):
    rays = [(cam.xyz, cam.get_landmark_direction(lm_name)) for lm_name in lm_names]
    z = 0
    best_z = None
    for step in (1, -0.1, 0.01, -0.001):
        loss = float("inf")
        while True:
            plane = ((0, 0, z), (0, 0, 1))
            if orientation == "horizontal":
                d = ml.get_distance(
                    ml.intersect_ray_and_plane(rays[0], plane),
                    ml.intersect_ray_and_plane(rays[1], plane)
                )
            else:
                base_point = ml.intersect_ray_and_plane(rays[0], plane)
                top_point = ml.intersect_ray_and_ray((base_point, (0, 0, 1)), rays[1])[1]
                d = ml.get_distance(base_point, top_point)
            delta = abs(size - d)
            if delta < loss:
                best_z = z
                loss = delta
            else:
                break
            z += step
    return best_z


def get_size(cam, lm_names, elevation, orientation):
    plane = ((0, 0, elevation), (0, 0, 1))
    if orientation == "horizontal":
        size = ml.get_distance(
            ml.intersect_ray_and_plane((cam.xyz, cam.get_landmark_direction(lm_names[0])), plane),
            ml.intersect_ray_and_plane((cam.xyz, cam.get_landmark_direction(lm_names[1])), plane),
        )
    else:
        base_point = ml.intersect_ray_and_plane(
            (cam.xyz, cam.get_landmark_direction(lm_names[0])),
            plane
        )
        top_point = ml.intersect_ray_and_ray(
            (base_point, (0, 0, 1)),
            (cam.xyz, cam.get_landmark_direction(lm_names[1]))
        )[1]
        size = ml.get_distance(base_point, top_point)
    return size


def get_silo(cam_panorama, silo_height, silo_ratio):
    lm_names = ["1500 Sonora Ave (Silo) (L)", "1500 Sonora Ave (Silo) (R)"]
    directions = [cam_panorama.get_landmark_direction(lm_name) for lm_name in lm_names]
    distance = 1000
    silo = None
    for step in (1, -0.1, 0.01, -0.001):
        loss = float("inf")
        while True:
            points = [ml.get_point(cam_panorama.xyz, direction, distance) for direction in directions]
            width = ml.get_distance(points[0], points[1])
            height = width * silo_ratio
            delta = abs(silo_height - height)
            if delta < loss:
                top = ml.get_midpoint(points)
                base = (top[0], top[1], top[2] - height)
                silo = {
                    "height": height,
                    "width": width,
                    "base": base,
                    "top": top,
                }
                loss = delta
            else:
                break
            distance += step
    return silo


def calibrate_panorama(
    cam_name="Ambrosia 02 (Panorama)",
    landmarks=[
        "FAA Miami ATCT (MIA)",  # via Vice Beach (B) & Leonida Keys 01 (Airplane) (X)
        # "MIA North Terminal Tower",  # via eonida Keys 01 (Airplane) (X) & Port Vice City (A)
    ],
    rays=[
        ("Port Vice City (A)", "Round Water Tower"),
        ("Port Vice City (A)", "MIA North Terminal Tower"),
        ("Leonida Keys 01 (Airplane) (X)", "MIA North Terminal Tower"),
        ["Leonida Keys 01 (Airplane) (X)", "Wheelabrator South Broward"],
        ("Leonida Keys 01 (Airplane) (X)", "Wheelabrator South Broward (NW)"),
        ("Loading Zone near Prison (S)", "3001 Gordon Hwy (Water Tower)"),
        ("WDNA FM Fake Cam", "WDNA FM (B)"),  # via Prison & Leonida Keys 01 (Airplane) (X)
    ],
    z_limits=(80, 100),
    panorama_hfov_range=np.arange(45.0, 51.51, 0.1),
    boxville_lm_names=("Red Boxville (BNE)", "Red Boxville (BNW)"),
    boxville_length=6.35,
):

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

    results = {}

    for hfov in panorama_hfov_range:

        json_filename=f"{dirname}/panorama {hfov=:.3f}.json"
        if not os.path.exists(json_filename):

            x = int(-2415 + (50 - hfov))
            y = int(5500 - (hfov - 50) * 100)
            #z = 92 - (hfov - 45) * 0.5
            #z_limits = (z - 0.5, z + 0.5)
            fixed_hfov = (hfov, hfov + 0.01, 1.0)

            cam, loss = ml.find_camera(
                cam_name,
                landmarks,
                rays,
                ((x, y - 100), (x, y + 100)), 15, 10,
                z_limits, (-4.5, -2.99, 0.001), fixed_hfov,
                "yanis", 1, map_area,
                None,
                f"{dirname}/panorama {hfov=:.3f} pass=1"
            )
            cam, loss = ml.find_camera(
                cam_name,
                landmarks,
                rays,
                (cam.xy, cam.xy), 10, 1.0,
                z_limits, (cam.pitch - 0.2, cam.pitch + 0.2, 0.001), fixed_hfov,
                "yanis", 1, map_area,
                None,
                f"{dirname}/panorama {hfov=:.3f} pass=2"
            )

            data = {
                "xyz": [float(x) for x in cam.xyz],
                "ypr": [float(x) for x in cam.ypr],
                "fov": [float(x) for x in cam.fov],
                "loss": float(loss),
            }

        else:
            with open(json_filename) as f:
                data = json.load(f)
            cam = ml.get_camera(cam_name)
            cam.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
            loss = data["loss"]

        data["boxville_z"] = get_elevation(cam, boxville_lm_names, boxville_length, "horizontal")
        silo = get_silo(cam, silo_height, silo_ratio)
        data["silo_z"] = silo["base"][2]
    
        with open(json_filename, "w") as f:
            json.dump(data, f, indent=4, sort_keys=True)

        results[str(hfov)] = data

    for name, key in [
        ("panorama loss", "loss"),
        ("panorama z", "xyz"),
        ("boxville z", "boxville_z")
    ]:
        filename = f"{dirname}/panorama {name}.png"
        if os.path.exists(filename): continue
        points = sorted(
            (float(hfov), result[key][2] if key == "xyz" else result[key])
            for hfov, result in results.items()
        )
        hfovs, values = zip(*points)
        plt.plot(hfovs, values, marker="o")
        plt.xlabel("panorama hfov")
        plt.ylabel(name)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(filename, dpi=300)
        plt.close()

    return results


def calibrate_bikers(
    cam_name="Ambrosia 01 (Bikers)",
    lm_names=["Billboard with Oval Motif #1"],
    rays=[("Ambrosia 02 (Panorama)", lm_name) for lm_name in [
        "Billboard with Diversity Motif (TE)",
        "Billboard with Diversity Motif (TW)",
        "Billboard with Irregular Shape",
        "Billboard with Irregular Shape (C)",
        "Billboard with Oval Motif #1 (TE)",
        "Billboard with Oval Motif #1 (TW)",
        "Large Billboard (Ambrosia)",
        "Large Billboard (Ambrosia) (TE)"
    ]],
    cam_street_delta_range=(0.5, 1.5)
):

    for hfov in panorama_hfov_range:

        json_filename_panorama = f"{dirname}/panorama {hfov=:.3f}.json"
        if not os.path.exists(json_filename_panorama): continue
        with open(json_filename_panorama) as f:
            data_panorama = json.load(f)

        #json_filename_postcard = f"{dirname}/postcars {hfov=:.3f}.json"
        #if not os.path.exists(json_filename_panorama): continue
        #with open(json_filename_panorama) as f:
        #    data_panorama = json.load(f)

        cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
        cam_panorama.set_xyz(data_panorama["xyz"]).set_ypr(data_panorama["ypr"]).set_fov(data_panorama["fov"]).register()

        json_filename = f"{dirname}/bikers {hfov=:.3f}.json"

        if not os.path.exists(json_filename):

            lm_name_b = "Billboard with Oval Motif #1 (B)"
            md.landmarks[lm_name_b] = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name_b)),
                ((0, 0, data_panorama["silo_z"]), (0, 0, 1))
            )
            lm_name = "Billboard with Oval Motif #1"
            md.landmarks[lm_name] = ml.intersect_ray_and_ray(
                (md.landmarks[lm_name_b], (0, 0, 1)),
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
            )[1]

            silo = get_silo(cam_panorama, silo_height, silo_ratio)
            xy = int(silo["top"][0]), int(silo["top"][1]) + 200
            z_range = data_panorama["silo_z"] + cam_street_delta_range[0], data_panorama["silo_z"] + cam_street_delta_range[1]

            cam, loss = ml.find_camera(
                cam_name,
                lm_names,
                rays,
                (xy, xy), 250, 10,
                z_range, (-1.0, 1.1, 0.1), (20.0, 45.1, 1.0),
                "yanis", 1, map_area,
                None,
                f"{dirname}/bikers {hfov=:.3f} pass 1"  
            )
            cam, loss = ml.find_camera(
                cam_name,
                lm_names,
                rays,
                (cam.xy, cam.xy), 25, 1,
                z_range, (cam.pitch - 0.5, cam.pitch + 0.5, 0.1), (cam.hfov - 2.5, cam.hfov + 2.6, 0.1),
                "yanis", 1, map_area,
                None,
                f"{dirname}/bikers {hfov=:.3f} pass 2"  
            )

            data = {
                "xyz": [float(x) for x in cam.xyz],
                "ypr": [float(x) for x in cam.ypr],
                "fov": [float(x) for x in cam.fov],
                "loss": float(loss),
            }

        else:

            with open(json_filename) as f:
                data = json.load(f)
            cam = ml.get_camera(cam_name)
            cam.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
            loss = data["loss"]

        filename = f"{dirname}/bikers {hfov=:.3f} final camera.png"
        if not os.path.exists(filename):
            cam.open()
            cam.render_all(loss=loss, no_landmarks=True)
            ml.AH = ml.AmbrosiaHill().render_on_camera(cam)
            cam.save(filename)

        with open(json_filename, "w") as f:
            json.dump(data, f, indent=4, sort_keys=True)


def calibrate_postcard(
    cam_name="Ambrosia Postcard (X)",
    landmarks=["1500 Sonora Ave (Silo)"],
    rays=[("Ambrosia 02 (Panorama)", lm_name) for lm_name in [
        "1500 Sonora Ave (Silo) (L)",
        "1500 Sonora Ave (Silo) (R)",
        "1500 Sonora Ave (Tank) (A)",
        "1500 Sonora Ave (Tank) (A) (L)",
        "1500 Sonora Ave (Tank) (A) (R)",
        "3400 Transmitter Rd",
        "3400 Transmitter Rd (B)",
        "US Sugar Mill (Factory) (NW)",
        "US Sugar Mill (Factory) (SE)",
        "USSM Smokestack (4)",
        "USSM Smokestack (5)",
        "USSM Smokestack (6)",
        "USSM Smokestack (7)",
        "USSM Smokestack (8)",
        "USSM Smokestack (9)",
        "USSM Smokestack (10)",
        "USSM Smokestack (11)",
        "White Silos (W) (NW)",
        "STA05",
        "STA20",
    ]],
    cylinders=[
        "1500 Sonora Ave (Silo) (L)",
        "1500 Sonora Ave (Silo) (R)",
        "1500 Sonora Ave (Tank) (A) (L)",
        "1500 Sonora Ave (Tank) (A) (R)",
    ],
    silo_height_range=np.arange(44.0, 45.01, 0.1),
    silo_ratio = 3.2,
    bison_lm_names=("Black Bison (1)", "Black Bison (2)"),
    bison_length=5.78,  # gta v: 5.48,
    worker_a_lm_names=("Worker A (Ambrosia) (B)", "Worker A (Ambrosia) (T)"),
    worker_a_height=1.80,
    worker_b_lm_names=("Worker B (Ambrosia) (B)", "Worker B (Ambrosia) (T)"),
    worker_b_height=1.70,
):

    for hfov in panorama_hfov_range:

        for postcard_hfov_delta in postcard_hfov_delta_range:
            postcard_hfov = hfov + postcard_hfov_delta

            json_filename_panorama=f"{dirname}/panorama {hfov=:.3f}.json"
            with open(json_filename_panorama) as f:
                data_panorama = json.load(f)
            cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
            cam_panorama.set_xyz(data_panorama["xyz"]).set_ypr(data_panorama["ypr"]).set_fov(data_panorama["fov"]).register()

            silo = get_silo(cam_panorama, silo_height, silo_ratio)
            md.landmarks["1500 Sonora Ave (Silo)"] = silo["top"]

            json_filename=f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f}.json"

            if not os.path.exists(json_filename):

                x, y, z = silo["top"]
                z_limits = (z - 5, z)
                fixed_hfov = (postcard_hfov, postcard_hfov + 0.01, 1.0)

                cam, loss = ml.find_camera(
                    cam_name,
                    landmarks,
                    rays,
                    ((int(x) + 25, int(y) + 100), (int(x) + 50, int(y) + 200)), 50, 5,
                    z_limits, (-4.0, 0.1, 0.1), fixed_hfov,
                    "yanis", 1, map_area,
                    None,
                    f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f} pass=1",
                    cylinders=cylinders
                )
                cam, loss = ml.find_camera(
                    cam_name,
                    landmarks,
                    rays,
                    (cam.xy, cam.xy), 25, 1,
                    (cam.z - 5.0, cam.z + 5.0), (cam.pitch - 2.0, cam.pitch + 2.01, 0.1), fixed_hfov,
                    "yanis", 1, map_area,
                    None,
                    f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f} pass=2",
                    cylinders=cylinders
                )

            else:

                with open(json_filename) as f:
                    data = json.load(f)
                cam = ml.get_camera(cam_name)
                cam.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
                loss = data["loss"]

            # needed for lollipop water tower
            cam_postcard = ml.get_camera(cam_name)
            cam_postcard.set_xyz(cam.xyz).set_ypr(cam.ypr).set_fov(cam.fov).register()

            lm_name = "3001 Gordon Hwy (Water Tower)"
            md.landmarks[lm_name] = ml.find_landmark("Loading Zone near Prison (S)", "Ambrosia 02 (Panorama)", lm_name)[0]
            for lm_name in [
                "3400 Transmitter Rd",
                "USSM Smokestack (1)",
                "USSM Smokestack (2)",
                "USSM Smokestack (4)",
                "USSM Smokestack (5)",
                "USSM Smokestack (6)",
                "USSM Smokestack (7)",
                "USSM Smokestack (8)",
                "USSM Smokestack (9)",
                "USSM Smokestack (10)",
                "USSM Smokestack (11)",
            ]:
                md.landmarks[lm_name] = ml.find_landmark(cam_panorama.name, cam_name, lm_name)[0]

            filename = f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f} final camera.png"
            if not os.path.exists(filename):
                cam.open()
                cam.render_all(loss=loss, no_landmarks=True)
                ml.GHWT = ml.GordonHighwayWaterTower().render_on_camera(cam)
                ml.SAS = ml.SonoraAvenueSilo(height=silo["height"]).render_on_camera(cam)
                ml.SASS = ml.SonoraAvenueSmokestacks().render_on_camera(cam)
                ml.SAT = ml.SonoraAvenueTanks().render_on_camera(cam)
                ml.TRWT = ml.TransmitterRoadWaterTower().render_on_camera(cam)
                cam.save(filename)

            silo_z = silo["base"][2]
            silo_boxville_delta = silo_z - data_panorama["boxville_z"]
            bison_z = get_elevation(cam, bison_lm_names, bison_length, "horizontal")
            bison_length_at_silo_z = get_size(cam, bison_lm_names, silo_z, "horizontal")
            bison_silo_delta = bison_z - silo_z
            worker_a_z = get_elevation(cam, worker_a_lm_names, worker_a_height, "vertical")
            worker_a_height_at_silo_z = get_size(cam, worker_a_lm_names, silo_z, "vertical")
            worker_a_silo_delta = worker_a_z - silo_z
            worker_b_z = get_elevation(cam, worker_b_lm_names, worker_b_height, "vertical")
            worker_b_height_at_silo_z = get_size(cam, worker_b_lm_names, silo_z, "vertical")
            worker_b_silo_delta = worker_b_z - silo_z

            result = {
                "xyz": [float(x) for x in cam.xyz],
                "ypr": [float(x) for x in cam.ypr],
                "fov": [float(x) for x in cam.fov],
                "loss": float(loss),
                "silo_z": silo_z,
                "silo_height": silo_height,
                "silo_boxville_delta": silo_boxville_delta,
                "bison_length": bison_length,
                "bison_length_at_silo_z": bison_length_at_silo_z,
                "bison_silo_delta": bison_silo_delta,
                "worker_a_height": worker_a_height,
                "worker_a_silo_delta": worker_a_silo_delta,
                "worker_a_height_at_silo_z": worker_a_height_at_silo_z,
                "worker_b_height": worker_b_height,
                "worker_b_height_at_silo_z": worker_b_height_at_silo_z,
                "worker_b_silo_delta": worker_b_silo_delta,
            }
            with open(json_filename, "w") as f:
                json.dump(result, f, indent=4, sort_keys=True)


def calibrate_fires(
    cam_name="Ambrosia 04 (Fires)",
    lm_names=[
        "1500 Sonora Ave (Tank) (A)",
        "Sunshine Skyway Bridge (N)",
        "Sunshine Skyway Bridge (S)",
        "3400 Transmitter Rd",
        "Wheelabrator South Broward (NW)",
    ],
    rays=[("Ambrosia 02 (Panorama)", lm_name) for lm_name in [
        "Dark Billboard (Ambrosia) (TE)",
        "Dark Billboard (Ambrosia) (TW)",
        "1500 Sonora Ave (Tank) (A) (L)",
        "1500 Sonora Ave (Tank) (A) (R)",
        "3400 Transmitter Rd (B)",
        "US Sugar Mill (Factory) (NW)",
        "US Sugar Mill (Factory) (SE)",
        "USSM Smokestack (4)",
        "USSM Smokestack (5)",
        "USSM Smokestack (6)",
        "USSM Smokestack (7)",
        "USSM Smokestack (8)",
        "USSM Smokestack (9)",
        "Wheelabrator South Broward (5B)",
    ]] + ([
        ["Chase (2) (A)", "Sunshine Skyway Bridge (S)"],
        ["Chase (2) (B)", "Sunshine Skyway Bridge (S)"],
    ] if False else []),
    cylinders=(
        "1500 Sonora Ave (Tank) (A) (L)",
        "1500 Sonora Ave (Tank) (A) (R)"
    ),
    silo_ratio=3.2,
    bobcat_length=5.78,
    bobcat_lm_names=("Car A (Ambrosia) (1)", "Car A (Ambrosia) (2)"),
):

    for hfov in panorama_hfov_range:

        for postcard_hfov_delta in postcard_hfov_delta_range:
            postcard_hfov = hfov + postcard_hfov_delta

            json_filename_panorama=f"{dirname}/panorama {hfov=:.3f}.json"
            with open(json_filename_panorama) as f:
                data_panorama = json.load(f)
            json_filename_postcard=f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f}.json"
            with open(json_filename_postcard) as f:
                data_postcard = json.load(f)

            cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
            cam_panorama.set_xyz(data_panorama["xyz"]).set_ypr(data_panorama["ypr"]).set_fov(data_panorama["fov"]).register()
            cam_postcard = ml.get_camera("Ambrosia Postcard (X)")
            cam_postcard.set_xyz(data_postcard["xyz"]).set_ypr(data_postcard["ypr"]).set_fov(data_postcard["fov"]).register()

            json_filename = f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f}.json"

            if not os.path.exists(json_filename):

                for lm_name in [
                    "1500 Sonora Ave (Tank) (A)",
                    "3400 Transmitter Rd",
                ]:
                    md.landmarks[lm_name] = ml.find_landmark(cam_panorama.name, cam_postcard.name, lm_name)[0]
                lm_name = "Wheelabrator South Broward (NW)"
                md.landmarks[lm_name] =  ml.find_landmark(cam_panorama.name, "Leonida Keys 01 (Airplane) (X)", lm_name)[0]

                ghwt = ml.find_landmark(cam_panorama.name, "Loading Zone near Prison (S)", "3001 Gordon Hwy (Water Tower)")[0]
                ss10 = ml.find_landmark(cam_panorama.name, cam_postcard.name, "USSM Smokestack (10)")[0]
                ss10[1] -= 1  # radius
                ss11 = ml.find_landmark(cam_panorama.name, cam_postcard.name, "USSM Smokestack (11)")[0]
                ss11[1] -= 1  # radius
                not_visible = [
                    (ghwt, (1260, 0, 3840, 2160)),
                    (ss10, (0, 0, 3840, 2160)),
                    (ss11, (0, 0, 3840, 2160)),
                ]
                xy = (-1250, int(3500 - (hfov - 50) * 25))

                cam, loss = ml.find_camera(
                    "Ambrosia 04 (Fires)",
                    lm_names,
                    rays,
                    (xy, xy), 500, 20,
                    (30, 75), (-4.0, 0.1, 0.2), (45.0, 75.1, 0.5),
                    "yanis", 1, map_area,
                    None,
                    f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f} pass 1",
                    not_visible=not_visible,
                    cylinders=cylinders,
                )
                if ml.get_distance(xy, cam.xy) > 350:
                    cam, loss = ml.find_camera(
                        "Ambrosia 04 (Fires)",
                        lm_names,
                        rays,
                        (cam.xy, cam.xy), 500, 20,
                        (30, 75), (-4.0, 0.1, 0.2), (45.0, 75.1, 0.5),
                        "yanis", 1, map_area,
                        None,
                        f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f} pass 1",
                        not_visible=not_visible,
                        cylinders=cylinders,
                    )
                cam, loss = ml.find_camera(
                    "Ambrosia 04 (Fires)",
                    lm_names,
                    rays,
                    (cam.xy, cam.xy), 100, 10,
                    (cam.z - 10, cam.z + 10), (cam.pitch - 2.0, cam.pitch + 2.01, 0.1), (cam.hfov - 4.0, cam.hfov + 4.01, 0.1),
                    "yanis", 1, map_area,
                    None,
                    f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f} pass 2",
                    not_visible=not_visible,
                    cylinders=cylinders,
                )
                cam, loss = ml.find_camera(
                    "Ambrosia 04 (Fires)",
                    lm_names,
                    rays,
                    (cam.xy, cam.xy), 25, 1,
                    (cam.z - 10, cam.z + 10), (cam.pitch - 1.01, cam.pitch + 1.01, 0.1), (cam.hfov - 2.0, cam.hfov + 2.01, 0.1),
                    "yanis", 1, map_area,
                    None,
                    f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f} pass 3",
                    not_visible=not_visible,
                    cylinders=cylinders,
                )

                data = {
                    "xyz": [float(x) for x in cam.xyz],
                    "ypr": [float(x) for x in cam.ypr],
                    "fov": [float(x) for x in cam.fov],
                    "loss": float(loss),
                }

            else:

                with open(json_filename) as f:
                    data = json.load(f)
                cam = ml.get_camera(cam_name)
                cam.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()
                loss = data["loss"]

            silo = get_silo(cam_panorama, silo_height, silo_ratio)
            md.landmarks["1500 Sonora Ave (Silo)"] = silo["top"]

            for lm_name in [
                "3400 Transmitter Rd",
                "USSM Smokestack (1)",
                "USSM Smokestack (2)",
                "USSM Smokestack (4)",
                "USSM Smokestack (5)",
                "USSM Smokestack (6)",
                "USSM Smokestack (7)",
                "USSM Smokestack (8)",
                "USSM Smokestack (9)",
                "USSM Smokestack (10)",
                "USSM Smokestack (11)",
            ]:
                md.landmarks[lm_name] = ml.find_landmark(cam_panorama.name, cam_postcard.name, lm_name)[0]

            filename = f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f} final camera.png"
            if not os.path.exists(filename):
                cam.open()
                cam.render_all(loss=loss, no_landmarks=True)
                ml.GHWT = ml.GordonHighwayWaterTower().render_on_camera(cam)
                ml.SAS = ml.SonoraAvenueSilo(height=silo["height"]).render_on_camera(cam)
                ml.SASS = ml.SonoraAvenueSmokestacks().render_on_camera(cam)
                ml.SAT = ml.SonoraAvenueTanks().render_on_camera(cam)
                ml.TRWT = ml.TransmitterRoadWaterTower().render_on_camera(cam)
                ml.SSB = ml.SunshineSkywayBridge().render_on_camera(cam)
                cam.save(filename)

            data["bobcat_z"] = get_elevation(cam, bobcat_lm_names, bobcat_length, "horizontal")

            with open(json_filename, "w") as f:
                json.dump(data, f, indent=4, sort_keys=True)

calibrate_panorama()
calibrate_bikers()
calibrate_postcard()
calibrate_fires()