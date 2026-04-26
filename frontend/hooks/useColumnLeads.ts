import { useInfiniteQuery } from "@tanstack/react-query";
import { leadsApi } from "@/lib/api";

interface Lead {
  id: number;
  business_name: string;
  category: string;
  city: string;
  total_score: number;
  status: string;
  email?: string;
  phone?: string;
}

interface LeadListResponse {
  total: number;
  items: Lead[];
  page: number;
  page_size: number;
}

const PAGE_SIZE = 50;

export function useColumnLeads(status: string) {
  return useInfiniteQuery<LeadListResponse, Error>({
    queryKey: ["leads", "kanban", status],
    queryFn: async ({ pageParam = 1 }) => {
      const res = await leadsApi.list({
        status,
        page: pageParam as number,
        page_size: PAGE_SIZE,
      });
      return res.data as LeadListResponse;
    },
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.page_size);
      if (lastPage.page < totalPages) {
        return lastPage.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    staleTime: 2 * 60 * 1000,
  });
}
