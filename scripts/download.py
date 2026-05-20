import argparse
import csv
import os
import praw
from tqdm import tqdm
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

def utc_iso(ts_utc: float) -> str:
    return datetime.fromtimestamp(ts_utc, tz=timezone.utc).isoformat()


def get_author(obj) -> str:
    try:
        a = obj.author
        return str(a) if a is not None else ""
    except Exception:
        return ""


def calculate_votes(score: int, ups: int | None) -> tuple[int, int]:
    if ups is None or score is None:
        return ("N/A", "N/A")
    
    downvotes = ups - score
    return (ups, max(0, downvotes))


def build_reddit_client() -> praw.Reddit:
    load_dotenv()

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "amc-disinformation-analysis/1.0")

    if not client_id or not client_secret:
        raise SystemExit(
            "Missing credentials. Set env vars:\n"
            "  REDDIT_CLIENT_ID\n"
            "  REDDIT_CLIENT_SECRET\n"
            "  REDDIT_USER_AGENT (optional)\n"
        )

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )
    reddit.read_only = True

    return reddit


def submissions_iter(subreddit, sort: str, limit: int):
    sort = sort.lower()
    if sort == "new":
        return subreddit.new(limit=limit)
    if sort == "hot":
        return subreddit.hot(limit=limit)
    if sort == "top":
        return subreddit.top(limit=limit)
    if sort == "rising":
        return subreddit.rising(limit=limit)
    if sort == "controversial":
        return subreddit.controversial(limit=limit)
    raise ValueError(f"Unsupported sort: {sort}")


def download():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subreddit", required=True, help="e.g. 'python' (no r/ prefix)")
    ap.add_argument("--n-posts", type=int, required=True, help="Number of POSTS to include (after filtering)")
    ap.add_argument("--sort", default="new", help="new|hot|top|rising|controversial (default: new)")
    ap.add_argument("--output", default=f"../data/data_dump{datetime.now().strftime("%Y%m%d%H%M")}.csv", help="Output CSV path")

    ap.add_argument(
        "--replace-more-limit",
        type=int,
        default=32,
        help="replace_more limit. 0=expand all. Use e.g. 32 to reduce volume. (default)",
    )
    ap.add_argument(
        "--max-comments-per-post",
        type=int,
        default=None,
        help="Optional cap: only write first K comments per post (after expanding).",
    )
    args = ap.parse_args()

    reddit = build_reddit_client()
    sub = reddit.subreddit(args.subreddit)

    fieldnames = [
        "activity_id",
        "activity_type",
        "timestamp",
        "subreddit",
        "author",
        "parent_id",
        "parent_type",
        "content",
        "permalink",
        "score",
        "upvotes",
        "downvotes",
        "upvote_ratio",
        "num_comments",
        "edited",
    ]

    post_iter = submissions_iter(sub, args.sort, limit=args.n_posts)

    written_posts = 0

    pbar = tqdm(total=args.n_posts, desc="Posts written", unit="post")

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()

        for submission in post_iter:
            if written_posts >= args.n_posts:
                break

            post_id = submission.name
            post_permalink = f"https://www.reddit.com{submission.permalink}"

            parts = [submission.title.strip()]
            if getattr(submission, "selftext", ""):
                st = submission.selftext.strip()
                if st:
                    parts.append(st)
            if getattr(submission, "url", ""):
                parts.append(f"URL: {submission.url}")
            post_content = "\n\n".join(parts).strip()

            upvote_ratio = getattr(submission, "upvote_ratio", None)
            ups = getattr(submission, "ups", None)
            upvotes, downvotes = calculate_votes(submission.score, ups)

            w.writerow(
                {
                    "activity_id": post_id,
                    "activity_type": "post",
                    "timestamp": utc_iso(submission.created_utc),
                    "subreddit": args.subreddit,
                    "author": get_author(submission),
                    "parent_id": "N/A",
                    "parent_type": "N/A",
                    "content": post_content,
                    "permalink": post_permalink,
                    "score": submission.score,
                    "upvotes": upvotes,
                    "downvotes": downvotes,
                    "upvote_ratio": upvote_ratio if upvote_ratio is not None else "",
                    "num_comments": submission.num_comments,
                    "edited": True if submission.edited else False,
                }
            )
            written_posts += 1

            if pbar is not None:
                pbar.update(1)
            else:
                print(f"Posts written: {written_posts}/{args.n_posts}")

            submission.comments.replace_more(limit=args.replace_more_limit)
            all_comments = submission.comments.list()
            if args.max_comments_per_post is not None:
                all_comments = all_comments[: args.max_comments_per_post]

            for c in all_comments:
                parent_id = c.parent_id
                parent_type = "post" if parent_id.startswith("t3_") else "comment"
                comment_permalink = f"https://www.reddit.com{c.permalink}"

                w.writerow(
                    {
                        "activity_id": c.name,
                        "activity_type": "comment",
                        "timestamp": utc_iso(c.created_utc),
                        "subreddit": args.subreddit,
                        "author": get_author(c),
                        "parent_id": parent_id,
                        "parent_type": parent_type,
                        "content": c.body,
                        "permalink": comment_permalink,
                        "score": c.score,
                        "upvotes": getattr(c, "ups", None),
                        "downvotes": "N/A",
                        "upvote_ratio": "N/A",
                        "num_comments": "N/A",
                        "edited": True if c.edited else False,
                    }
                )

    pbar.close()


if __name__ == "__main__":
    download()