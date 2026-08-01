import React from "react";
import AgentsExperience from "../../components/rag/AgentsExperience";

const UserAgentsPage = () => (
  <AgentsExperience
    title="My AI Agents"
    subtitle="Ask questions about your department's documents"
    emptyText="Your IT team hasn't deployed any AI agents for your department yet. Check back later!"
    basePath="/user/agents"
  />
);

export default UserAgentsPage;
