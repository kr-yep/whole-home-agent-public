"""Streamlit demo for explicit local D0 persistence and bounded free-text queries."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.errors import B0Error
from whole_home_agent.memory_query import answer_latest_memory
from whole_home_agent.public_demo import run_public_demo


DEMO_DATABASE = Path(".whole-home-agent/demo-memory.sqlite3")


def main() -> None:
    st.set_page_config(page_title="Whole Home Agent — Local Memory", page_icon="🏠")
    st.title("Whole Home Agent · Local Memory")
    st.caption("Durable D0 replay + bounded free-text location query")
    st.error(
        "OPERATE DISABLED · Stores only the included synthetic replay; no camera, "
        "upload, cloud, household data, or device action"
    )
    st.write(
        "先把附帶的八秒合成影片結果寫入本機 SQLite，再用中文或英文詢問物品位置。"
    )

    if st.button("建立／更新示範記憶", type="primary"):
        try:
            result = run_public_demo(
                replay_run_id="public-b1-memory-ui-001",
                include_frames=False,
                archive=SQLiteReplayArchive(DEMO_DATABASE),
            )
            st.success(f"記憶狀態：{result['archive']['status']}")
        except B0Error as error:
            st.error(f"無法建立示範記憶：{error.error_code.value}")

    question = st.text_input("詢問位置", value="鑰匙在哪裡？")
    if st.button("詢問記憶"):
        if not DEMO_DATABASE.is_file():
            st.warning("請先建立示範記憶。")
        else:
            try:
                result = answer_latest_memory(
                    SQLiteReplayArchive(DEMO_DATABASE), question
                )
                st.success(result["presentation"]["text"])
                st.caption(
                    f"subject={result['answer']['subject_id']} · "
                    f"status={result['answer']['status']} · "
                    f"scope={result['answer']['world_scope']}"
                )
                with st.expander("結構化答案與證據鏈"):
                    st.json(result["answer"])
            except B0Error as error:
                st.error(f"無法回答：{error.error_code.value}")

    st.info(
        "可選 LLM 僅支援明確選擇的本機 loopback OpenAI-compatible API；"
        "預設回答完全不需要模型或 API key。"
    )


if __name__ == "__main__":
    main()
