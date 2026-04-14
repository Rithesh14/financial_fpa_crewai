from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool  # Use crewai.tools instead of crewai_tools to avoid Weaviate issues

from fpa_tools.fpa_operations import run_fpa_analysis
from fpa_tools.chart_tools import (
    generate_revenue_trend_chart,
    generate_scenario_comparison_chart,
    generate_risk_dashboard,
    generate_profitability_analysis_chart
)
from fpa_tools.pdf_generator import generate_pdf_report

# FPA Analysis Tool
@tool
def fpa_analysis_tool(csv_path: str):
    """
    Run FP&A analysis on financial statements.
    
    Args:
        csv_path: Path to the CSV file containing financial data
        
    Returns:
        Structured financial metrics including:
        - avg_revenue_growth: Average revenue growth rate
        - avg_ebitda_margin: Average EBITDA margin
        - avg_operating_cash_flow: Average operating cash flow
        - avg_debt_equity: Average debt-to-equity ratio
        - avg_current_ratio: Average current ratio
        - scenarios: Best/base/worst case revenue scenarios
    """
    return run_fpa_analysis(csv_path)


@CrewBase
class FinancialFpa():
	"""FinancialFpa crew - Enterprise Financial Analysis with AI Agents"""

	agents_config = 'config/agents.yaml'
	tasks_config = 'config/tasks.yaml'

	# ===== AGENTS =====
	
	@agent
	def fpa_analyst(self) -> Agent:
		"""FP&A Analyst - Historical performance analysis"""
		return Agent(
			config=self.agents_config['fpa_analyst'],
			tools=[
				fpa_analysis_tool,
				generate_revenue_trend_chart,
				generate_profitability_analysis_chart
			],
			verbose=True
		)

	@agent
	def scenario_analyst(self) -> Agent:
		"""Scenario Analyst - Forward-looking projections"""
		return Agent(
			config=self.agents_config['scenario_analyst'],
			tools=[
				fpa_analysis_tool,
				generate_scenario_comparison_chart
			],
			verbose=True
		)

	@agent
	def risk_analyst(self) -> Agent:
		"""Risk Analyst - Financial stability assessment"""
		return Agent(
			config=self.agents_config['risk_analyst'],
			tools=[
				fpa_analysis_tool,
				generate_risk_dashboard
			],
			verbose=True
		)

	@agent
	def market_researcher(self) -> Agent:
		"""Market Researcher - Industry benchmarks and competitive intelligence"""
		# Note: Internet search tools (SerperDevTool, ScrapeWebsiteTool) are disabled
		# due to Weaviate dependency issues. The agent will provide analysis based
		# on the provided data and general industry knowledge from the LLM.
		
		return Agent(
			config=self.agents_config['market_researcher'],
			tools=[],  # No external tools - uses LLM knowledge only
			verbose=True
		)

	@agent
	def cfo_advisor(self) -> Agent:
		"""CFO Advisor - Executive synthesis and recommendations"""
		return Agent(
			config=self.agents_config['cfo_advisor'],
			tools=[generate_pdf_report],
			verbose=True
		)

	# ===== TASKS =====
	
	@task
	def performance_analysis_task(self) -> Task:
		"""Analyze historical financial performance"""
		return Task(
			config=self.tasks_config['performance_analysis_task'],
		)

	@task
	def market_research_task(self) -> Task:
		"""Research industry benchmarks and market context"""
		return Task(
			config=self.tasks_config['market_research_task'],
		)

	@task
	def scenario_planning_task(self) -> Task:
		"""Create forward-looking scenarios"""
		return Task(
			config=self.tasks_config['scenario_planning_task'],
		)

	@task
	def risk_assessment_task(self) -> Task:
		"""Assess financial risks and stability"""
		return Task(
			config=self.tasks_config['risk_assessment_task'],
		)

	@task
	def chart_generation_task(self) -> Task:
		"""Generate visual charts and graphs"""
		return Task(
			config=self.tasks_config['chart_generation_task'],
		)

	@task
	def cfo_advisory_task(self) -> Task:
		"""Synthesize insights into executive summary"""
		return Task(
			config=self.tasks_config['cfo_advisory_task'],
		)

	@task
	def pdf_generation_task(self) -> Task:
		"""Generate comprehensive PDF report"""
		return Task(
			config=self.tasks_config['pdf_generation_task'],
		)

	# ===== CREW =====
	
	@crew
	def crew(self) -> Crew:
		"""
		Creates the FinancialFpa crew with collaboration enabled.
		
		Process Flow:
		1. Performance Analysis (FPA Analyst)
		2. Market Research (Market Researcher)
		3. Scenario Planning (Scenario Analyst)
		4. Risk Assessment (Risk Analyst)
		5. Chart Generation (FPA Analyst)
		6. CFO Advisory (CFO Advisor)
		7. PDF Generation (CFO Advisor)
		"""

		return Crew(
			agents=self.agents,  # All agents with allow_delegation=True
			tasks=self.tasks,    # All 7 tasks in sequence
			process=Process.sequential,
			verbose=True,
			# Agents can collaborate via delegation and questions
		)
