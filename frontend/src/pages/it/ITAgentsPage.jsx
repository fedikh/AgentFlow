import React from "react";
import AgentsExperience from "../../components/rag/AgentsExperience";

/**
 * ITAgentsPage — lets IT preview the DEPLOYED agents exactly as end users see
 * them (chat + documents). Reuses the end-user experience; only ACTIVE spaces
 * are shown.
 */
const ITAgentsPage = () => (
  <AgentsExperience
    title="Deployed Agents"
    subtitle="Preview your deployed agents exactly as your end users see them"
    emptyText="You haven't deployed any agents yet. Deploy a space from RAG Spaces to preview it here."
    onlyDeployed
    basePath="/it/agents"
  />
);

export default ITAgentsPage;
