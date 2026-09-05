"""Generate 24 versioned RGB stress clips and independently scripted event labels."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples/media/generated"
SUITE = OUT / "ablation_v2.suite.json"
SCENARIOS = ("stationary", "move", "contain", "take_out", "occlusion", "disappear")
WIDTH, HEIGHT, FPS, COUNT = 640, 360, 10, 80


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def scene(kind, variant):
    t, start, stop = 25 + variant * 2, 40 + variant, 55 + variant
    remove = 68 + variant
    moving = kind in ("move", "contain", "take_out")
    events = []
    def event(frame, operation, subject, predicate, target):
        events.append(dict(event_id=f"event-{len(events)}", frame_index=frame,
                           operation=operation, subject_id=subject, predicate=predicate, object_id=target))
    if kind in ("contain", "take_out"):
        event(t, "assert", "key", "inside", "bag")
    if moving:
        event(stop, "assert", "bag", "at_zone", "sofa")
    if kind == "take_out":
        event(remove, "retract", "key", "inside", "bag")
    frames = []
    for index in range(COUNT):
        ratio = max(0, min(1, (index - start) / (stop - start))) if moving else 0
        x = round(240 + variant * 3 + ratio * (455 - 240 - variant * 3))
        bag = [x, 215 + variant, x + 92, 287 + variant]
        key = [100 + variant * 5, 245, 128 + variant * 5, 257]
        if kind in ("contain", "take_out", "occlusion") and t - 8 <= index < t:
            key = [x + 32, 242 + variant, x + 60, 254 + variant]
        if kind in ("contain", "take_out") and index >= t:
            key = None
        if kind == "take_out" and index >= remove:
            key = [350, 150, 378, 162]
        if kind == "occlusion" and t <= index < t + 1 + variant % 2:
            key = None
        if kind == "disappear" and index >= t:
            key = None
        frames.append({"bag": bag, "key": key, "sofa": [400, 185, 610, 310]})
    queries = []
    for index in sorted({t - 1, t + 1, t + 6, stop + 6, COUNT - 1}):
        for subject in ("key", "bag"):
            found = moving and index >= stop + 6 and (subject == "bag" or
                    kind in ("contain", "take_out") and not (kind == "take_out" and index >= remove))
            queries.append(dict(frame=index, subject=subject, status="FOUND" if found else "UNKNOWN",
                                location="sofa" if found else None))
    return frames, events, queries


def draw(state):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (WIDTH, HEIGHT), (224, 216, 197))
    painter = ImageDraw.Draw(image)
    sofa, bag, key = state["sofa"], state["bag"], state["key"]
    painter.rounded_rectangle(sofa, radius=20, fill=(95, 111, 132), outline=(45, 57, 72), width=5)
    painter.rectangle((sofa[0]+15, sofa[1]+30, sofa[2]-15, sofa[3]-12), fill=(117,137,160))
    painter.rounded_rectangle(bag, radius=10, fill=(45,112,170), outline=(20,52,90), width=4)
    if key:
        painter.ellipse((key[0],key[1],key[0]+12,key[1]+12), outline=(126,86,0), width=4)
        painter.rectangle((key[0]+10,key[1]+4,key[2],key[1]+8), fill=(231,176,24))
        painter.rectangle((key[2]-6,key[1]+7,key[2]-2,key[3]), fill=(231,176,24))
    return image


def generate():
    import av
    if SUITE.exists() or list(OUT.glob("ablation_v2_*.manifest.json")):
        raise FileExistsError("v2 artifacts already exist; do not overwrite frozen evidence")
    clips = []
    for kind in SCENARIOS:
        for variant in range(4):
            name = f"ablation_v2_{kind}_{variant}"
            states, events, queries = scene(kind, variant)
            media, annotations, manifest = [OUT / (name + suffix) for suffix in
                                            (".mp4", ".annotations.json", ".manifest.json")]
            with av.open(str(media), mode="w", format="mp4") as container:
                stream = container.add_stream("libx264", rate=FPS)
                stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
                stream.options = {"crf": "18", "preset": "fast", "threads": "1"}
                for index, state in enumerate(states):
                    frame = av.VideoFrame.from_image(draw(state))
                    frame.pts, frame.time_base = index, Fraction(1, FPS)
                    for packet in stream.encode(frame):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)
            write_json(annotations, dict(schema_version=1, coordinate_space="pixel_xyxy_exclusive",
                       width=WIDTH, height=HEIGHT, frames=[dict(frame_index=i, objects=s) for i,s in enumerate(states)]))
            split = "train" if variant < 2 else "test"
            write_json(manifest, dict(schema_version=1, source_id=name, source_revision="1",
                source_kind="recorded_video", timestamp_basis="media_pts", use_class="D0_SYNTHETIC",
                path=media.name, sha256=digest(media), license="CC0-1.0",
                provenance=dict(kind="project_generated_synthetic", generator="tools/generate_ablation_v2.py",
                                generator_sha256=digest(Path(__file__))),
                frame_count=COUNT, width=WIDTH, height=HEIGHT, fps=dict(numerator=FPS,denominator=1),
                annotations=dict(path=annotations.name, sha256=digest(annotations)),
                entities=[dict(entity_id=k,label=k,instance_count=1) for k in ("key","bag","sofa")],
                events=events, split=split))
            clips.append(dict(name=name, scenario=kind, variant=variant, split=split,
                              manifest=manifest.name, manifest_hash=digest(manifest), queries=queries))
    write_json(SUITE, dict(schema_version=1, clips=clips, limitations="procedural RGB, not real household footage"))
    print(f"Generated {len(clips)} clips; suite SHA256 {digest(SUITE)}")


if __name__ == "__main__":
    generate()
