/**
 * Unified Buffer snapshot — channels + posts + dailyPostingLimits in one call.
 * All Content Studio tabs read from this single endpoint to minimize Buffer API hits.
 */
import { NextRequest, NextResponse } from "next/server";
import {
  bufferQuery,
  getOrgId,
  getRateLimitHint,
} from "@/lib/buffer";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const postLimit = parseInt(searchParams.get("limit") || "200", 10);

  try {
    const orgId = await getOrgId();

    if (!orgId) {
      const hint = getRateLimitHint();
      return NextResponse.json(
        {
          channels: [],
          posts: [],
          limits: [],
          rate_limited: !!hint,
          rate_limit: hint
            ? { window: hint.window, reset_at: hint.resetEstimate }
            : null,
          error: hint
            ? "Buffer API rate-limited — no cached data available yet."
            : "No organization id available.",
        },
        { status: 200 }
      );
    }

    const today = new Date().toISOString().split("T")[0];

    // Single GraphQL with three top-level fields — Buffer batches them server-side.
    const query = `
      query Snapshot {
        snapshot_channels: channels(input: { organizationId: "${orgId}" }) {
          id
          name
          service
          isDisconnected
        }
        snapshot_posts: posts(
          input: {
            organizationId: "${orgId}"
            filter: { status: [draft, needs_approval, scheduled, sending, sent, error] }
            sort: [{ field: createdAt, direction: desc }]
          }
          first: ${postLimit}
        ) {
          edges {
            node {
              id
              text
              status
              dueAt
              sentAt
              createdAt
              channelId
              channelService
              channel { name }
              assets { source thumbnail mimeType }
              error { message }
              externalLink
            }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    `;

    const result = await bufferQuery<any>(
      query,
      `buffer:snapshot:v2:${orgId}:${postLimit}`,
      5 * 60 * 1000
    );

    const channels = result.data?.snapshot_channels || [];
    const rawPosts = result.data?.snapshot_posts?.edges?.map((e: any) => e.node) || [];
    const pageInfo = result.data?.snapshot_posts?.pageInfo || {
      hasNextPage: false,
      endCursor: null,
    };

    // Limits: separate query because dailyPostingLimits has different shape.
    // Skip if we have no channel ids OR if rate-limited (avoid extra call).
    let limits: any[] = [];
    if (channels.length > 0 && !result.rateLimited) {
      const activeIds = channels
        .filter((c: any) => !c.isDisconnected)
        .map((c: any) => c.id);
      if (activeIds.length > 0) {
        const limitsResult = await bufferQuery<any>(
          `{
            dailyPostingLimits(input: {
              organizationId: "${orgId}"
              channelIds: [${activeIds.map((id: string) => `"${id}"`).join(", ")}]
              date: "${today}"
            }) {
              channelId
              sent
              scheduled
              limit
            }
          }`,
          `buffer:limits:v2:${orgId}:${today}`,
          5 * 60 * 1000
        );
        const rawLimits = limitsResult.data?.dailyPostingLimits || [];
        limits = rawLimits.map((l: any) => {
          const ch = channels.find((c: any) => c.id === l.channelId);
          return { ...l, name: ch?.name, service: ch?.service };
        });
      }
    } else if (result.rateLimited) {
      // Try to serve stale limits if available
      const stale = await bufferQuery<any>(
        `__unused__`,
        `buffer:limits:v2:${orgId}:${today}`,
        0
      );
      if (stale.data?.dailyPostingLimits) {
        limits = stale.data.dailyPostingLimits.map((l: any) => {
          const ch = channels.find((c: any) => c.id === l.channelId);
          return { ...l, name: ch?.name, service: ch?.service };
        });
      }
    }

    return NextResponse.json({
      channels,
      posts: rawPosts,
      limits,
      pageInfo,
      stale: result.stale,
      rate_limited: result.rateLimited,
      rate_limit: result.rateLimited
        ? {
            window: result.rateLimitWindow,
            reset_at: result.rateLimitResetAt,
          }
        : null,
      fetched_at: new Date().toISOString(),
    });
  } catch (err: any) {
    const hint = getRateLimitHint();
    return NextResponse.json(
      {
        channels: [],
        posts: [],
        limits: [],
        rate_limited: !!hint,
        rate_limit: hint
          ? { window: hint.window, reset_at: hint.resetEstimate }
          : null,
        error: err.message || "Unknown error",
      },
      { status: 200 }
    );
  }
}
