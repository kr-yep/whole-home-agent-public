"""Streamlit demo for explicit local D0 persistence and bounded free-text queries."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.errors import B0Error
from whole_home_agent.memory_query import answer_latest_memory, list_known_entities
from whole_home_agent.public_demo import run_public_demo


DEMO_DATABASE = Path(".whole-home-agent/demo-memory.sqlite3")

# Display-only labels. The askable vocabulary always comes from the stored replay.
_ENTITY_LABELS = {"key": "🔑 鑰匙", "bag": "👜 包包", "sofa": "🛋 沙發"}
_ENTITY_WORDS = {"key": "鑰匙", "bag": "包包", "sofa": "沙發"}
_PREDICATE_WORDS = {"inside": "在…裡面", "at_zone": "位於"}


def _label(entity_id: str) -> str:
    return _ENTITY_LABELS.get(entity_id, entity_id)


def _word(entity_id: str) -> str:
    return _ENTITY_WORDS.get(entity_id, entity_id)


def _build_memory() -> None:
    try:
        result = run_public_demo(
            replay_run_id="public-b1-memory-ui-001",
            include_frames=False,
            archive=SQLiteReplayArchive(DEMO_DATABASE),
        )
        st.session_state["build_status"] = result["archive"]["status"]
    except B0Error as error:
        st.session_state["build_status"] = None
        st.error(f"無法建立示範記憶：{error}")


def _render_chain(answer: dict) -> None:
    """Show the evidence as a chain, because the chain is the actual product."""

    steps = answer.get("relation_path") or []
    if not steps:
        return
    chain = _label(steps[0]["subject_id"])
    for step in steps:
        predicate = _PREDICATE_WORDS.get(step["predicate"], step["predicate"])
        chain += f" &nbsp;──*{predicate}*──▸&nbsp; " + _label(step["object_id"])
    st.markdown("**它憑什麼這樣說**")
    st.markdown(chain, unsafe_allow_html=True)
    for index, step in enumerate(steps, start=1):
        st.caption(f"{index}. `{step['source_claim_id']}` · 第 {step['source_sequence']} 筆")


def _render_answer(result: dict) -> None:
    answer = result["answer"]
    st.success(result["presentation"]["text"])
    _render_chain(answer)
    st.caption(
        f"subject={answer['subject_id']} · status={answer['status']} · "
        f"{answer['epistemic_status']} · scope={answer['world_scope']}"
    )
    with st.expander("原始結構化答案"):
        st.json(answer)


def _render_rejection(error: B0Error, entity_ids: tuple[str, ...]) -> None:
    """Say which rule was hit and what to try, not just the error code."""

    st.warning(f"這句我沒辦法回答：{error}")
    details = getattr(error, "details", None) or {}
    matched = details.get("matched_entity_count")
    if matched is not None and matched > 1:
        st.info("一次只能問一個東西。")
    elif matched == 0:
        st.info(
            "這句話裡沒有我認得的東西。目前只有："
            + "、".join(_word(item) for item in entity_ids)
        )
    else:
        st.info(
            "我只回答「東西在哪」。可以用「在哪」「哪裡」「位置」「放哪」「找」這類問法；"
            "目前還不支援「在不在沙發上」這種是非題，也不能操作任何裝置。"
        )


def main() -> None:
    st.set_page_config(page_title="Whole Home Agent — Local Memory", page_icon="🏠")
    st.title("Whole Home Agent · Local Memory")
    st.caption("這段八秒合成重播的持久記憶 · 回答是估計值，不是真實住家")
    st.error(
        "OPERATE DISABLED · 僅存入內附的合成重播；無攝影機、上傳、雲端、住家資料或裝置動作"
    )

    if not DEMO_DATABASE.is_file():
        st.write("這個示範還沒有記憶。先把內附的八秒合成影片結果寫入本機 SQLite。")
        if st.button("建立示範記憶", type="primary"):
            _build_memory()
            st.rerun()
        return

    if st.session_state.pop("build_status", None):
        st.toast("記憶已更新")

    archive = SQLiteReplayArchive(DEMO_DATABASE)
    try:
        entity_ids = list_known_entities(archive)
    except B0Error as error:
        st.error(f"無法讀取記憶：{error}")
        return

    st.write("**我現在認得這些東西**，點一下就問：")
    for column, entity_id in zip(st.columns(len(entity_ids)), entity_ids):
        if column.button(_label(entity_id), key=f"chip-{entity_id}", use_container_width=True):
            st.session_state["question"] = f"{_word(entity_id)}在哪裡？"
            st.session_state["auto_ask"] = True
            st.rerun()

    st.text_input("或自己打一句", key="question", placeholder="鑰匙在哪裡？")
    asked = st.button("詢問記憶", type="primary") or st.session_state.pop("auto_ask", False)

    if asked:
        question = st.session_state.get("question", "")
        try:
            _render_answer(answer_latest_memory(archive, question))
        except B0Error as error:
            _render_rejection(error, entity_ids)

    with st.expander("重建示範記憶"):
        st.caption("重跑內附影片並覆寫本機 SQLite。內容相同時為 UNCHANGED。")
        if st.button("重建"):
            _build_memory()
            st.rerun()

    st.caption(
        "可選 LLM 僅支援明確選擇的本機 loopback OpenAI-compatible 端點，且只負責把已算好的"
        "答案講成句子；預設回答完全不需要模型。"
    )


if __name__ == "__main__":
    main()
