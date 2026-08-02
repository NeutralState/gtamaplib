
import json
import os
import sys

import numpy as np

from gtamaplib import gtamaplib as ml
from gtamaplib import gtamapdata as md
from gtamaplib import gtamaputils as mu


def get_landmark_size(cam, center_xyz, dir_a, dir_b):
    cam_xyz = np.asarray(cam.xyz, float)
    center_xyz = np.asarray(center_xyz, float)
    dir_a = np.asarray(dir_a, float)
    dir_b = np.asarray(dir_b, float)
    diff = center_xyz - cam_xyz
    depth = np.linalg.norm(diff)
    normal = diff / depth
    cos_a = np.dot(dir_a, normal)
    cos_b = np.dot(dir_b, normal)
    # intersection points on the frontal plane at the same depth
    point_a = cam_xyz + (depth / cos_a) * dir_a
    point_b = cam_xyz + (depth / cos_b) * dir_b
    return float(np.linalg.norm(point_a - point_b))

def get_marker_size(lm_name):
    return 9 if lm_name in [
        "Radio Tower (Ambrosia)",
        "1500 Sonora Ave (Silo)",
        "1500 Sonora Ave (Tank) (A)",
        "US Sugar Mill (Factory) (NW)",
        "US Sugar Mill (Factory) (SE)",
    ] else 3 if "USSM Smokestack" in lm_name else 6


dirname = "ambrosia"

panorama_hfov_range = np.arange(45.0, 52.1, 0.5)
postcard_hfov_delta_range = np.arange(-4.0, 2.1, 0.5)
highres =  len(sys.argv) > 1 and "--highres" in sys.argv
if highres:
    panorama_hfov_range = np.arange(50.5, 51.01, 0.1)
    postcard_hfov_delta_range = np.arange(0.9, 1.41, 0.1)

boxville_lake_delta = -0.5
bobcat_canal_delta = -6.0



lm_names_postcard = [
    "3400 Transmitter Rd",
    "3400 Transmitter Rd (B)",
    #"1500 Sonora Ave (Silo) (N)",
    "1500 Sonora Ave (Tank) (A)",
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
    #"STA08",
    #"STA09",
    #"STA10",
    #"STA11",
    #"STA12",
    #"STA14",
    #"STA15",
    #"STA16",
    #"STA17",
    "STA20",
    #"STA21",
    #"STA22",
    #"STA23",
    #"STA24",
    #"STR03",
    #"STR04",
    #"STR05",
]

bobcat_length = 5.78

for hfov in panorama_hfov_range:
    for postcard_hfov_delta in postcard_hfov_delta_range:
        postcard_hfov = hfov + postcard_hfov_delta

        json_filename = f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f}.json"
        if not os.path.exists(json_filename): continue
        with open(json_filename) as f:
            data = json.load(f)
        cam = ml.get_camera("Ambrosia 04 (Fires)")
        cam.set_xyz(data["xyz"]).set_ypr(data["ypr"]).set_fov(data["fov"]).register()

        lm_name = "Sunshine Skyway Bridge (S)"
        ssbs = md.landmarks[lm_name]
        p, a, b, d, _ = ml.intersect_ray_and_ray(
            (cam.xyz, cam.get_landmark_direction(lm_name)),
            (ssbs, (0, 0, 1))
        )
        data["ssbs_d"] = d

        lm_names = "Car A (Ambrosia) (1)", "Car A (Ambrosia) (2)"
        rays = [(cam.xyz, cam.get_landmark_direction(lm_name)) for lm_name in lm_names]
        z = 0
        for step in (1, -0.1, 0.01, -0.001):
            loss_ = float("inf")
            while True:
                plane = ((0, 0, z), (0, 0, 1))
                d = ml.get_distance(
                    ml.intersect_ray_and_plane(rays[0], plane),
                    ml.intersect_ray_and_plane(rays[1], plane)
                )
                delta_ = abs(bobcat_length - d)
                if delta_ < loss_:
                    bobcat_z = z
                    loss_ = delta_
                else:
                    break
                z += step
        data["bobcat_z"] = bobcat_z
        lm_names = "Car A (Ambrosia) (1)", "Car A (Ambrosia) (2)"
        rays = [(cam.xyz, cam.get_landmark_direction(lm_name)) for lm_name in lm_names]
        plane = ((0, 0, bobcat_z), (0, 0, 1))
        car_b_length = ml.get_distance(
            ml.intersect_ray_and_plane(rays[0], plane),
            ml.intersect_ray_and_plane(rays[1], plane)
        )
        data["car_b_length"] = car_b_length
        with open(json_filename, "w") as f:
            json.dump(data, f, indent=4, sort_keys=True)


candidates_only = len(sys.argv) > 1 and "--candidates" in sys.argv
candidates = [
    #(50.7, 1.0),
    #(50.7, 1.2),
    #(50.8, 1.0),
    #(50.8, 1.1),
    #(50.8, 1.2),
    #(50.9, 1.0),
    #(50.9, 1.1),
    #####(50.9, 1.2),
    #(50.9, 1.3),
]
candidates_count = 0

best = (50.9, 1.2)

d = 100
image_filename = f"{dirname}/ambrosia {'candidates' if candidates_only else 'highres' if highres else 'all'}.png"

m = ml.get_map("yanis")
m.open(scale=2 if candidates or highres else 1)
map_area = (-7000, 0, -500, 6500)


for i, hfov in enumerate(panorama_hfov_range):
    hfov_image_filename = f"{dirname}/ambrosia {hfov=:.3f}.png"
    #filename = f"triangulate/ambrosia lake leonida {hfov=:.3f}.png"
    #if os.path.exists(filename): continue

    for j, postcard_hfov_delta in enumerate(postcard_hfov_delta_range):
        postcard_hfov = hfov + postcard_hfov_delta

        if candidates_only and (round(hfov, 1), round(postcard_hfov_delta, 1)) not in candidates: continue

        json_filename_panorama = f"{dirname}/panorama {hfov=:.3f}.json"
        if not os.path.exists(json_filename_panorama): continue
        with open(json_filename_panorama) as f:
            data_panorama = json.load(f)
        json_filename_bikers = f"{dirname}/bikers {hfov=:.3f}.json"
        if not os.path.exists(json_filename_bikers): continue
        with open(json_filename_bikers) as f:
            data_bikers = json.load(f)
        json_filename_postcard = f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f}.json"
        if not os.path.exists(json_filename_postcard): continue
        with open(json_filename_postcard) as f:
            data_postcard = json.load(f)
        json_filename_fires = f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f}.json"
        if not os.path.exists(json_filename_fires): continue
        with open(json_filename_fires) as f:
            data_fires = json.load(f)

        lake_z = data_panorama['boxville_z'] + boxville_lake_delta

        cam_panorama = ml.get_camera("Ambrosia 02 (Panorama)")
        cam_panorama.set_xyz(data_panorama["xyz"]).set_ypr(data_panorama["ypr"]).set_fov(data_panorama["fov"]).register()
        cam_bikers = ml.get_camera("Ambrosia 01 (Bikers)")
        cam_bikers.set_xyz(data_bikers["xyz"]).set_ypr(data_bikers["ypr"]).set_fov(data_bikers["fov"]).register()
        cam_postcard = ml.get_camera("Ambrosia Postcard (X)")
        cam_postcard.set_xyz(data_postcard["xyz"]).set_ypr(data_postcard["ypr"]).set_fov(data_postcard["fov"]).register()
        cam_fires = ml.get_camera("Ambrosia 04 (Fires)")
        cam_fires.set_xyz(data_fires["xyz"]).set_ypr(data_fires["ypr"]).set_fov(data_fires["fov"]).register()

        loprwt_z = ml.find_landmark(cam_panorama.name, "Loading Zone near Prison (S)", "3001 Gordon Hwy (Water Tower)")[0][2]
        #llpwt_y = ml.find_landmark(cam_panorama.name, cam_postcard.name, "3400 Transmitter Rd")[0][1]
        mean = (data_panorama['loss'] + data_bikers['loss'] + data_postcard['loss'] + data_fires['loss']) / 4
        #if mean >= 3.0: continue

        """
        print(
            f"fov_pbpf={hfov:.3f}, {data_bikers['fov'][0]:.3f}, {data_postcard['fov'][0]:.3f}, {data_fires['fov'][0]:.3f} "
            f"loss_pbpf={data_panorama['loss']:.3f}, {data_bikers['loss']:.3f}, {data_postcard['loss']:.3f}, {data_fires['loss']:.3f} "
            f"mean={mean:.3f} "
            f"silo_h={data_panorama['silo']['h']:.3f} silo_z={data_panorama['silo']['br'][2]:.3f} bikers_z={data_bikers['xyz'][2]:.3f} "
            f"boxville_z={data_panorama['boxville_z']:.3f} bobcat_z={data_fires['bobcat_z']:.3f} "
            f"bison_z={data_postcard['bison_z']:.3f} bison_l={data_postcard['bison_l_at_silo_z']:.3f} "
            f"worker_z={data_postcard['worker_z']:.3f} worker_h={data_postcard['worker_h_at_silo_z']:.3f} "
            f"bison_silo_d={data_postcard['bison_z']-data_panorama['silo']['br'][2]:.3f} "
            f"ssbs_d={data_fires['ssbs_d']:.3f} loprwt_z={loprwt_z:.3f} "
            #f"ussm_d={data_postcard['ussm_d']:.3f} llpwt_d={data_postcard['llpwt_d']:.3f}""
            #f"silo_wh={data_panorama['silo_wh'][0]:.3f}, {data_panorama['silo_wh'][1]:.3f} "
        )
        """

        if candidates_only:
            color = ml.get_rgb(candidates_count * 360 / len(candidates), 1.0, 0.75)
        else:
            color = (0, 255, 255) if mean < 3.0 \
                else (0, 255, 0) if mean < 4.0 \
                else (255, 255, 0) if mean < 8.0 \
                else (255, 0, 0) if mean < 16.0 \
                else (255, 0, 255) if mean < 32.0 \
                else (0, 0, 255) if mean < 64.0 \
                else (0, 255, 255)
        color_hfov = ml.get_rgb(j * 360 / len(list(postcard_hfov_delta_range)), 1.0, 0.75)
        landmarks = {}
        # LAKE
        points = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            lm_name = f"Lake Leonida ({letter})"
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, lake_z), (0, 0, 1))
            )
            points.append(point)
            if len(points) > 1:
                m.draw_line((points[-2], points[-1]), color, 2)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        points = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            lm_name = f"Island LLA ({letter})"
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, lake_z), (0, 0, 1))
            )
            points.append(point)
            if len(points) > 1 and letter != "Y":
                m.draw_line((points[-2], points[-1]), color, 2)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        points = []
        for letter in "ABCDEFGHIJKA":
            lm_name = f"Island LLB ({letter})"
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, lake_z), (0, 0, 1))
            )
            points.append(point)
            if len(points) > 1 and letter != "Y":
                m.draw_line((points[-2], points[-1]), color, 2)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        # CANAL
        for lm_name in ["Ambrosia Bridge (3B)", "Ambrosia Bridge (4B)"]:
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, lake_z), (0, 0, 1))
            )
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        # ROADS
        points = []
        for letter in "EDCBAZYXWV":
            lm_name = f"Ambrosia Main St ({letter})"
            z = data_postcard["silo_z"]
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, z), (0, 0, 1))
            )
            points.append(point)
            if len(points) > 1:
                m.draw_line((points[-2], points[-1]), color, 2)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        points = []
        for letter in "YZ":
            lm_name = f"Route 35 ({letter})"
            z = data_postcard["silo_z"]
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, z), (0, 0, 1))
            )
            points.append(point)
            if len(points) > 1:
                m.draw_line((points[-2], points[-1]), color, 2)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        # ORLANDO STATION
        z = data_postcard["silo_z"]
        for lm_name in ["Orlando Station (BC)", "Orlando Station (BW)"]:
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, z), (0, 0, 1))
            )
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        # PANORAMA
        for lm_name in ["Red Boxville (BNE)", "Red Boxville (BNW)", "Billboard with Oval Motif #1 (B)"]:
            z = data_panorama["boxville_z"] if "Boxville" in lm_name else data_postcard["silo_z"]
            point = ml.intersect_ray_and_plane(
                (cam_panorama.xyz, cam_panorama.get_landmark_direction(lm_name)),
                ((0, 0, z), (0, 0, 1))
            )
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name)
        lm_name = "Round Water Tower"
        point = ml.find_landmark(cam_panorama.name, "Port Vice City (A)", lm_name)[0]
        m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
        landmarks[lm_name] = (point, cam_panorama.name)
        # BIKERS
        for lm_name in ["Ambrosia Hill (TW)", "Ambrosia Hill (TE)"]:
            direction = cam_bikers.get_landmark_direction(lm_name)
            target = ml.get_point(cam_bikers.xyz, direction, 2000)
            m.draw_line((cam_bikers.xy, target), color, 1)
        # POSTCARD
        for lm_name in lm_names_postcard + ["1500 Sonora Ave (Silo)"]:
            if "STA" in lm_name or "STR" in lm_name or "USSM" in lm_name:
                continue
            point = ml.find_landmark(cam_panorama.name, cam_postcard.name, lm_name)[0]
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name, cam_postcard.name)
        z = data_postcard["silo_z"]
        lm_names = [
            "Black Bison (1)",
            "Black Bison (2)",
            "Guard Booth (Ambrosia) (E)",
            "Guard Booth (Ambrosia) (N)",
            "Guard Booth (Ambrosia) (W)",
            "Train Signal (Ambrosia) (2WB)",
            "Train Tracks (Ambrosia) (A)",
            "Train Tracks (Ambrosia) (B)",
            "Train Tracks (Ambrosia) (C)",
            "Worker A (Ambrosia) (B)",
            "Worker B (Ambrosia) (B)",
        ]
        for lm_name in lm_names:
            point = ml.intersect_ray_and_plane(
                (cam_postcard.xyz, cam_postcard.get_landmark_direction(lm_name)),
                ((0, 0, z), (0, 0, 1))
            )
            landmarks[lm_name] = (point, cam_postcard.name)
        m.draw_line((landmarks["Train Tracks (Ambrosia) (A)"][0], landmarks["Train Tracks (Ambrosia) (B)"][0]), color, 1)
        m.draw_line((landmarks["Train Tracks (Ambrosia) (B)"][0], landmarks["Train Tracks (Ambrosia) (C)"][0]), color, 1)
        for lm_name in lm_names:
            m.draw_circle(landmarks[lm_name][0], get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
        # TRAIN SIGNALS
        lm_name = "Train Signal (Ambrosia) (2W)"
        point = ml.intersect_ray_and_ray(
            (cam_postcard.xyz, cam_postcard.get_landmark_direction(lm_name)),
            (landmarks["Train Signal (Ambrosia) (2WB)"][0], (0, 0, 1))
        )[0]
        landmarks[lm_name] = (point, cam_postcard.name)
        ts_z = point[2]
        for lm_name in [
            "Train Signal (Ambrosia) (1E)", "Train Signal (Ambrosia) (1W)",
            "Train Signal (Ambrosia) (2E)",
            "Train Signal (Ambrosia) (3E)", "Train Signal (Ambrosia) (3W)",
            "Train Signal (Ambrosia) (4E)", "Train Signal (Ambrosia) (4W)",
        ]:
            point = ml.intersect_ray_and_plane(
                (cam_postcard.xyz, cam_postcard.get_landmark_direction(lm_name)),
                ((0, 0, ts_z), (0, 0, 1))
            )
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_postcard.name)
        # SUGAR MILL, WATER TOWERS
        for lm_name in [
            "1500 Sonora Ave (Tank) (A)", "3400 Transmitter Rd"
        ]:
            point = ml.find_landmark(cam_panorama.name, cam_postcard.name, lm_name)[0]
            for cam in (cam_panorama, cam_postcard, cam_fires):
                direction = cam.get_landmark_direction(lm_name)
                distance = ml.get_distance(cam.xyz, point)
                target = ml.get_point(cam.xyz, direction, distance)
                m.draw_line((cam.xy, target), color, 1)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_panorama.name, cam_postcard.name)
        cam_names = ["Loading Zone near Prison (S)", "Ambrosia 02 (Panorama)"]
        lm_name = "3001 Gordon Hwy (Water Tower)"
        point = ml.find_landmark(cam_names[0], cam_names[1], lm_name)[0]
        m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
        landmarks[lm_name] = (point, cam_names[0], cam_names[1])
        # FACTORIES, WHEELABRATOR
        for cam, lm_name in [
            (cam_postcard, "Factory A (Ambrosia) (N)"),
            (cam_postcard, "Factory A (Ambrosia) (S)"),
            (cam_postcard, "Factory D (Ambrosia) (NW)"),
            #(cam_panorama, "Wheelabrator South Broward (NW)")
        ]:
            point = ml.find_landmark(cam.name, cam_fires.name, lm_name)[0]
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam.name, cam_fires.name)
        cam_names = ["Leonida Keys 01 (Airplane) (X)", "Ambrosia 02 (Panorama)"]
        for lm_name in [
            "Wheelabrator South Broward", "Wheelabrator South Broward (TE)",
            "Wheelabrator South Broward (TW)", "Wheelabrator South Broward (NW)"
        ]:
            point = ml.find_landmark(cam_names[0], cam_names[1], lm_name)[0]
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_names[0], cam_names[1])
        # FIRES
        lm_names = [
            lm_name for lm_name in list(cam_fires.landmark_pixels)
            if lm_name.startswith("Building") or lm_name.startswith("Canal") or lm_name.startswith("Car")
            or lm_name.startswith("Road") or lm_name.startswith("Path")
            or lm_name == "Radio Tower (Ambrosia) (B)"
        ]
        for lm_name in lm_names:
            z = data_fires["bobcat_z"] + (bobcat_canal_delta if "Car C" in lm_name or "Canal C" in lm_name or "Road E" in lm_name else 0)
            point = ml.intersect_ray_and_plane(
                (cam_fires.xyz, cam_fires.get_landmark_direction(lm_name)),
                ((0, 0, z), (0, 0, 1))
            )
            for lm_name_b in lm_names:
                split = " (South Ambrosia) " if " (South Ambrosia) " in lm_name else " (Ambrosia) "
                parts, parts_b = lm_name.split(split), lm_name_b.split(split)
                name, name_b = parts[0], parts_b[0]
                number, number_b = None, None
                try:
                    number, number_b = int(parts[1][-2]), int(parts_b[1][-2])
                except IndexError, ValueError:
                    pass
                if name == name_b and number and number == number_b - 1:
                    z = data_fires["bobcat_z"] + (bobcat_canal_delta if "Car C" in lm_name_b or "Canal C" in lm_name_b or "Road E" in lm_name_b else 0)
                    point_b = ml.intersect_ray_and_plane(
                        (cam_fires.xyz, cam_fires.get_landmark_direction(lm_name_b)),
                        ((0, 0, z), (0, 0, 1))
                    )
                    m.draw_line((point, point_b), color, 1)
            m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
            landmarks[lm_name] = (point, cam_fires.name)
        lm_name = "Radio Tower (Ambrosia)"
        point = ml.intersect_ray_and_ray(
            (cam_fires.xyz, cam_fires.get_landmark_direction(lm_name)),
            (landmarks["Radio Tower (Ambrosia) (B)"][0], (0, 0, 1))
        )[0]
        m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
        landmarks[lm_name] = (point, cam_fires.name)
        # CAMERAS
        m.draw_camera(cam_panorama, d=d)
        text = f"{hfov:.1f}"[1]
        m.draw_circle(cam_panorama.xyz, 12, color, (255, 255, 255), 1, text)
        m.draw_camera(cam_bikers, d=d)
        m.draw_circle(data_bikers["xyz"], 12, color, (255, 255, 255), 1, text)
        m.draw_camera(cam_postcard, d=d)
        if candidates_only:
            text = "ABCDEFGHIJKLM"[candidates_count]
        else:
            text = f"{hfov:.1f}"[1]
        m.draw_circle(data_postcard["xyz"], 12, color, (255, 255, 255), 1, text)
        m.draw_camera(cam_fires, d=d)
        m.draw_circle(data_fires["xyz"], 12, color, (255, 255, 255), 1, text)
        # LANDMARKS
        all_lm_names = (
            list(md.pixels[cam_panorama.name]) + list(md.pixels[cam_bikers.name]) +
            list(md.pixels[cam_postcard.name]) + list(md.pixels[cam_fires.name])
        )
        all_lm_names = [
            lm_name for lm_name in all_lm_names
            if lm_name not in landmarks and all_lm_names.count(lm_name) > 1
            and not lm_name.startswith("STA") and not lm_name.startswith("STR")
            and not lm_name.endswith(" (L)") and not lm_name.endswith(" (R)")
        ]
        for lm_name in all_lm_names:
            cams = [cam_panorama, cam_postcard, cam_fires]
            if "USSM" in lm_name and all(lm_name in md.pixels[cam.name] for cam in cams):
                rays = [(cam.xyz, cam.get_landmark_direction(lm_name)) for cam in cams if cam is not cam_fires]  ## FIXME!
                point = ml.intersect_rays(rays)[0]
                m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
                landmarks[lm_name] = (point, cams[0].name, cams[1].name, cams[2].name)
        for lm_name in all_lm_names:
            for cam_names in [
                (cam_panorama.name, cam_bikers.name),
                (cam_panorama.name, cam_fires.name),
                (cam_postcard.name, cam_fires.name),
                (cam_panorama.name, cam_postcard.name),
            ]:
                if lm_name not in landmarks and lm_name in md.pixels[cam_names[0]] and lm_name in md.pixels[cam_names[1]]:
                    point = ml.find_landmark(cam_names[0], cam_names[1], lm_name)[0]
                    m.draw_circle(point, get_marker_size(lm_name), color, (255, 255, 255), 1, ml.get_letter(lm_name))
                    landmarks[lm_name] = (point, cam_names[0], cam_names[1])

        for lm_name, data in sorted(landmarks.items()):
            md.landmarks[lm_name] = data[0]
        ml.AH = ml.AmbrosiaHill()
        ml.GHWT = ml.GordonHighwayWaterTower()
        ml.SAS = ml.SonoraAvenueSilo()
        ml.SASS = ml.SonoraAvenueSmokestacks()
        ml.TRWT = ml.TransmitterRoadWaterTower()
        """
        if mean < 3.0:
            for k, cam in enumerate([cam_panorama, cam_bikers, cam_postcard, cam_fires]):
                string = ["panorama", "bikers", "postcard", "fires"][k]
                loss = [data_panorama["loss"], data_bikers["loss"], data_postcard["loss"], data_fires["loss"]][k]
                # it's okay to render multiple panos and bikers - landmark locations will be different
                filename = f"{dirname}/{string} {hfov=:.3f},{postcard_hfov:.3f} {street=:.3f} final camera.png"
                if not os.path.exists(filename): ### or True: ####
                    cam.render_grid((-2800, 3750, -2700, 4250), 1, data_panorama['silo']['br'][2])
                    if cam == cam_fires:
                        cam.render_grid((-5400, 3450, -5300, 3550), 1, 65.9)
                    cam.render_all().render_camera_info(loss=loss)
                    #render_silo(cam, data_panorama["silo"]["tc"], data_panorama["silo"]["h"])
                    cam.save(filename)
        """

        if best and best == (round(hfov, 1), round(postcard_hfov_delta, 1)):
            for camera in [cam_panorama, cam_bikers, cam_postcard, cam_fires]:
                print(camera)
            for lm_name, data in sorted(landmarks.items()):
                (x, y, z), cam_names = data[0], data[1:]
                if len(cam_names) == 1:
                    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_names[0]}')
                elif len(cam_names) == 2:
                    (x, y, z), a, b, d, _ = ml.find_landmark(cam_names[0], cam_names[1], lm_name)
                    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # d={d:.3f} via {cam_names[0]} & {cam_names[1]}')
                else:
                    print(f'    "{lm_name}": ({x:.3f}, {y:.3f}, {z:.3f}),  # via {cam_names[0]}, {cam_names[1]} & {cam_names[2]}')

            print(f"{lake_z=}")
            filename = f"{dirname}/ambrosia panorama {hfov=:.3f},{postcard_hfov:.3f} lake_z={lake_z:.3f} projection.png"
            if not os.path.exists(filename):
                m = ml.get_map("yanis")
                x, y, z = cam_panorama.xyz
                cam_panorama.set_xyz((x, y, z - lake_z)).register()
                # ml.get_camera.cache_clear()
                m.project_camera_parallel(cam_panorama.name, map_area)
                m.save(filename, map_area)
            print(f"{lake_z=}")
            filename = f"{dirname}/ambrosia fires {hfov=:.3f},{postcard_hfov:.3f} bobcat_z={data_fires['bobcat_z']:.3f} projection.png"
            if not os.path.exists(filename):
                m = ml.get_map("yanis")
                x, y, z = cam_fires.xyz
                cam_fires.set_xyz((x, y, z - bobcat_z)).register()
                # ml.get_camera.cache_clear()
                m.project_camera_parallel(cam_fires.name, map_area)
                m.save(filename, map_area)

        if candidates_only:
            candidates_count += 1
    

m.save(image_filename, map_area)