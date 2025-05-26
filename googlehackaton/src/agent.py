
import src.datamodel as dm

from langgraph.graph import END, START, StateGraph

import src.node as nodes


class TripAgent:
    """
    """

    def __init__(self):
        """
    
        """
        self.init()

    def init(self):
        """Initialize the agent."""
        self.create_graph()


    def create_graph(self):
        """Create the workflow graph for the agent.

        Returns:
            StateGraph: A compiled StateGraph object representing the agent's workflow.
        """
        # Create the graph
        workflow = StateGraph(dm.GraphState)
        # Create nodes
        workflow.add_node("extract_data", nodes.extract_data)
        workflow.add_node("check_data", nodes.check_trip)
        workflow.add_node("get_coordinates", nodes.get_coordinates)
        workflow.add_node("plan_trip_entur", nodes.plan_trip_entur)

        # Create edges
        # Route is a conditional node
        workflow.add_edge(START, "extract_data")
        workflow.add_conditional_edges(
            "extract_data", 
            nodes.check_trip, 
        {
            "True": "get_coordinates",
            "False": END,
        })
        workflow.add_edge("get_coordinates", "plan_trip_entur")
        workflow.add_edge("plan_trip_entur", END)

        return workflow.compile()



if __name__ == "__main__":

    import asyncio

    async def test_agent():
        Agent = TripAgent()
        app = Agent.create_graph()
        question = {
            "question": "Jeg skal reise fra Jernbanetorget, til Gladengveien 10. Jeg bruker rullestol. Jeg vil reise kl 12:00 i dag.",
        }
        # Create a ChatPromptTemplate of the question
        ans = await app.ainvoke(question)
        print(ans)

    # Run the async function
    asyncio.run(test_agent())
