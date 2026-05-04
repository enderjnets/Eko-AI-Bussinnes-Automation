"use client";

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { metadataApi } from "@/lib/api";

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
}

interface WorkspaceContextValue {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  isLoading: boolean;
  setCurrentWorkspace: (workspace: Workspace | null) => void;
  refreshWorkspaces: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue>({
  currentWorkspace: null,
  workspaces: [],
  isLoading: false,
  setCurrentWorkspace: () => {},
  refreshWorkspaces: () => {},
});

export function useWorkspace() {
  return useContext(WorkspaceContext);
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [currentWorkspace, setCurrentWorkspaceState] = useState<Workspace | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const res = await fetch("/api/v1/workspaces/", {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
        },
      });
      if (!res.ok) throw new Error("Failed to load workspaces");
      return res.json() as Promise<{ items: Workspace[] }>;
    },
    enabled: typeof window !== "undefined" && !!localStorage.getItem("access_token"),
  });

  const workspaces = data?.items || [];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem("workspace_id");
    if (saved && workspaces.length > 0) {
      const found = workspaces.find((w) => w.id === saved);
      if (found && (!currentWorkspace || currentWorkspace.id !== found.id)) {
        setCurrentWorkspaceState(found);
      }
    } else if (workspaces.length > 0 && !currentWorkspace) {
      setCurrentWorkspaceState(workspaces[0]);
      localStorage.setItem("workspace_id", workspaces[0].id);
    }
  }, [workspaces, currentWorkspace]);

  const setCurrentWorkspace = useCallback((workspace: Workspace | null) => {
    setCurrentWorkspaceState(workspace);
    if (workspace) {
      localStorage.setItem("workspace_id", workspace.id);
    } else {
      localStorage.removeItem("workspace_id");
    }
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        currentWorkspace,
        workspaces,
        isLoading,
        setCurrentWorkspace,
        refreshWorkspaces: refetch,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}
