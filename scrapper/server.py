import os
from pathlib import Path
from typing import Tuple

import gradio as gr

from app import (
    fetch_threads_posts,
    fetch_threads_from_rss,
    fetch_telegram_posts,
    save_posts,
    THREADS_USERNAME,
    THREADS_RSS,
)


def sync_now() -> str:
    """Run the full sync: Threads (RSS or username) + Telegram, then save to DB.
    Returns a short status string for the UI.
    """
    try:
        posts = []

        if THREADS_RSS:
            posts += fetch_threads_from_rss(THREADS_RSS)
        elif THREADS_USERNAME:
            posts += fetch_threads_posts(THREADS_USERNAME)

        posts += fetch_telegram_posts()

        if not posts:
            return "No posts found to save"

        res = save_posts(posts)
        return res
    except Exception as e:
        return f"Error: {e}"


def main() -> None:
    iface = gr.Interface(
        fn=sync_now,
        inputs=[],
        outputs="text",
        title="Social Sync",
        description="Click the button to fetch Threads + Telegram posts and save them to Supabase",
    )

    # Read optional basic auth credentials from env to protect the UI.
    basic_user = os.getenv("BASIC_AUTH_USER")
    basic_pass = os.getenv("BASIC_AUTH_PASS")
    auth = None
    if basic_user and basic_pass:
        auth = (basic_user, basic_pass)

    # Launch (0.0.0.0 so it is reachable when deployed/dockerized)
    # Pass `auth` so Gradio will require a username/password if provided.
    iface.launch(server_name="0.0.0.0", server_port=7860, auth=auth)


if __name__ == "__main__":
    main()
