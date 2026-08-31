"""Streamlit presentation for the single allowlisted public B1 replay."""

from __future__ import annotations

import streamlit as st

from whole_home_agent.public_demo import load_public_demo_media, run_public_demo


def main() -> None:
    st.set_page_config(
        page_title="Whole Home Agent — Offline Replay",
        page_icon="🏠",
        layout="wide",
    )
    st.title("Whole Home Agent")
    st.caption("Evidence-bound object memory — fixed synthetic replay")
    st.error(
        "OPERATE DISABLED · No live camera, uploads, household data, cloud, or device actions"
    )
    st.info(
        "This demo analyzes one project-generated 8-second clip. Every answer is an "
        "estimate scoped to that replay, not a claim about a real home."
    )

    with st.spinner("Running the fixed offline replay…"):
        result = run_public_demo(include_frames=True)

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("1 · Fixed public replay")
        st.video(load_public_demo_media(), format="video/mp4")
        st.caption(
            f"{result['source']['source_id']}@{result['source']['source_revision']} · "
            f"{result['source']['frame_count']} frames · {result['source']['license']}"
        )
    with right:
        st.subheader("2 · Ask: Where is the key?")
        st.success(result["answer_summary"])
        answer = result["answer"]
        st.metric("Answer status", answer["status"])
        metric_columns = st.columns(3)
        metric_columns[0].metric("Location", answer["location_id"] or "unknown")
        metric_columns[1].metric("Epistemic", answer["epistemic_status"])
        metric_columns[2].metric(
            "Evidence steps", len(answer["relation_path"])
        )
        st.caption(
            f"Scope: {answer['world_scope']} · run: {answer['replay_run_id']} · "
            f"as-of sequence: {answer['as_of_source_sequence']}"
        )

    st.subheader("3 · What the system connected")
    claims = result["claims"]
    st.dataframe(
        [
            {
                "frame": item["source_position"]["frame_index"],
                "estimate": (
                    f"{item['operation']} {item['predicate']}("
                    f"{item['subject_id']}, {item['object_id']})"
                ),
                "confidence floor": item["evidence"][0]["confidence"],
                "evidence frames": (
                    f"{item['evidence'][0]['start']['frame_index']} → "
                    f"{item['evidence'][0]['end']['frame_index']}"
                ),
                "status": item["epistemic_status"],
            }
            for item in claims
        ],
        width="stretch",
        hide_index=True,
    )

    quality = result["perception_evaluation"]["quality"]
    relation_quality = result["relation_evaluation"]["quality"]
    cost = result["perception_evaluation"]["cost"]
    st.subheader("4 · Fixed-fixture evaluation (not indoor evidence)")
    metric_columns = st.columns(5)
    metric_columns[0].metric("AP50", f"{quality['ap50']:.3f}")
    metric_columns[1].metric("mAP50:95", f"{quality['map50_95']:.3f}")
    metric_columns[2].metric("Key recall", f"{quality['key_recall50']:.3f}")
    metric_columns[3].metric("Event F1", f"{relation_quality['f1']:.3f}")
    metric_columns[4].metric("Detector p95", f"{cost['detector_latency_p95_ms']:.1f} ms")
    st.warning(result["perception_evaluation"]["evidence_limit"])

    st.subheader("5 · Abstention behavior")
    abstentions = result["source_diagnostics"]["abstentions"]
    if abstentions:
        st.dataframe(abstentions, width="stretch", hide_index=True)
    else:
        st.write(
            "No abstention was needed in this replay. Ambiguous, unsupported, "
            "and interrupted cases are covered by fail-closed tests."
        )

    notable_frames = [
        {
            "frame": item["frame_index"],
            "detected": ", ".join(
                detection["label"] for detection in item["detections"]
            ),
            "bound": ", ".join(item["bound_entity_ids"]),
            "emitted claims": ", ".join(item["emitted_claim_ids"]),
        }
        for item in result["frames"]
        if item["emitted_claim_ids"] or item["frame_index"] in {0, 28, 35, 65, 79}
    ]
    with st.expander("Replay timeline and notable frames"):
        st.dataframe(notable_frames, width="stretch", hide_index=True)
    with st.expander("Traceable answer JSON"):
        st.json(result["answer"])
    with st.expander("Run receipt"):
        st.json(result["run_receipt"])
    with st.expander("Evidence limits"):
        for warning in result["warnings"]:
            st.write(f"- {warning}")


if __name__ == "__main__":
    main()
