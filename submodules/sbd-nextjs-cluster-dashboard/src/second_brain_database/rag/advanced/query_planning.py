"""Advanced RAG Features - Intelligent Query Planning.

This module implements a sophisticated query planning system designed to handle complex,
multi-faceted information needs. It analyzes incoming queries, decomposes them into
manageable sub-queries, and orchestrates their execution using optimal retrieval strategies.

The system supports various query types and execution strategies:
- **Query Decomposition**: Breaking down complex questions into atomic sub-queries.
- **Dependency Management**: Handling execution order where one query depends on another's result.
- **Strategy Selection**: Automatically choosing between direct, iterative, or hierarchical retrieval.
- **Result Synthesis**: Combining results from multiple sub-queries into a coherent answer.

Key Components:
- `IntelligentQueryPlanner`: The main engine for analysis and orchestration.
- `QueryPlan`: A structured blueprint for executing a complex query.
- `QueryType` & `QueryStrategy`: Enums defining the classification and execution logic.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.exceptions import RAGError
from second_brain_database.rag.core.types import DocumentChunk, QueryRequest, QueryResponse

logger = get_logger()


class QueryType(str, Enum):
    """Enumeration of supported query types.

    Classifies the nature of the user's information need to determine the best
    processing strategy.

    Attributes:
        SIMPLE: Direct factual query requiring single-step retrieval.
        COMPLEX: Multi-part query requiring decomposition.
        COMPARATIVE: Request to compare two or more entities or concepts.
        TEMPORAL: Query involving time, history, or chronological order.
        CAUSAL: Query asking for reasons, causes, or effects.
        PROCEDURAL: How-to or step-by-step instructions.
        ANALYTICAL: Deep analysis or evaluation of a topic.
        MULTI_DOMAIN: Query spanning multiple distinct knowledge domains.
    """
    SIMPLE = "simple"
    COMPLEX = "complex"
    COMPARATIVE = "comparative"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    PROCEDURAL = "procedural"
    ANALYTICAL = "analytical"
    MULTI_DOMAIN = "multi_domain"


class QueryStrategy(str, Enum):
    """Enumeration of query execution strategies.

    Defines the structural approach to executing a query plan.

    Attributes:
        DIRECT: Single retrieval step (best for Simple queries).
        DECOMPOSED: Break into independent or dependent sub-queries.
        ITERATIVE: Refine search based on initial results (feedback loop).
        HIERARCHICAL: Top-down approach (Overview -> Details).
        EXPLORATORY: Broad search followed by focused analysis.
    """
    DIRECT = "direct"
    DECOMPOSED = "decomposed"
    ITERATIVE = "iterative"
    HIERARCHICAL = "hierarchical"
    EXPLORATORY = "exploratory"


@dataclass
class SubQuery:
    """A single unit of work within a larger query plan.

    Represents an atomic query that can be executed against the vector store.

    Attributes:
        id (str): Unique identifier for the sub-query.
        text (str): The actual query text to be executed.
        query_type (QueryType): The type of this specific sub-query.
        priority (int): Execution priority (lower number = higher priority).
        depends_on (List[str]): IDs of other sub-queries that must complete first.
        expected_result_type (str): Hint about the expected output format.
        metadata (Dict[str, Any]): Additional context or parameters.
    """
    id: str
    text: str
    query_type: QueryType
    priority: int
    depends_on: List[str]
    expected_result_type: str
    metadata: Dict[str, Any]


@dataclass
class QueryPlan:
    """A comprehensive execution plan for a complex query.

    Contains all the information needed to orchestrate the retrieval and
    synthesis process.

    Attributes:
        plan_id (str): Unique identifier for the plan.
        original_query (str): The user's original input query.
        query_type (QueryType): The detected classification of the query.
        strategy (QueryStrategy): The selected execution strategy.
        sub_queries (List[SubQuery]): List of all sub-queries to execute.
        execution_order (List[str]): Ordered list of sub-query IDs defining the workflow.
        estimated_complexity (float): Heuristic score of plan complexity (0.0-1.0).
        estimated_duration_seconds (float): Estimated time to complete execution.
        metadata (Dict[str, Any]): Plan metadata (creation time, user prefs, etc.).
    """
    plan_id: str
    original_query: str
    query_type: QueryType
    strategy: QueryStrategy
    sub_queries: List[SubQuery]
    execution_order: List[str]
    estimated_complexity: float
    estimated_duration_seconds: float
    metadata: Dict[str, Any]


@dataclass
class QueryExecution:
    """State tracking for a running query plan.

    Maintains the runtime state, results, and metrics of a plan execution.

    Attributes:
        plan_id (str): ID of the plan being executed.
        status (str): Current status ('running', 'completed', 'failed').
        current_step (int): Index of the current step in execution_order.
        completed_sub_queries (List[str]): IDs of completed sub-queries.
        results (Dict[str, Any]): Map of sub-query IDs to their results.
        start_time (datetime): Timestamp when execution started.
        end_time (Optional[datetime]): Timestamp when execution finished.
        total_chunks_retrieved (int): Total number of document chunks fetched.
        error_message (Optional[str]): Error details if execution failed.
    """
    plan_id: str
    status: str
    current_step: int
    completed_sub_queries: List[str]
    results: Dict[str, Any]
    start_time: datetime
    end_time: Optional[datetime]
    total_chunks_retrieved: int
    error_message: Optional[str]


class IntelligentQueryPlanner:
    """Intelligent query planning system for complex RAG operations.

    This class serves as the brain of the advanced RAG system. It uses heuristics
    and pattern matching (and potentially LLMs) to understand the structure of a
    user's question and design a bespoke retrieval strategy.

    Attributes:
        max_sub_queries (int): Hard limit on sub-queries to prevent explosion.
        max_complexity (float): Threshold for rejecting overly complex plans.
        parallel_execution (bool): Whether to run independent sub-queries concurrently.
        query_patterns (Dict[QueryType, List[str]]): Regex patterns for query classification.
    """
    
    def __init__(
        self,
        max_sub_queries: int = 10,
        max_complexity: float = 1.0,
        parallel_execution: bool = True
    ):
        """Initialize the query planner with configuration limits.

        Args:
            max_sub_queries (int): Maximum number of sub-queries to generate. Defaults to 10.
            max_complexity (float): Maximum complexity threshold. Defaults to 1.0.
            parallel_execution (bool): Enable parallel execution. Defaults to True.
        """
        self.max_sub_queries = max_sub_queries
        self.max_complexity = max_complexity
        self.parallel_execution = parallel_execution
        
        # Query pattern definitions
        self.query_patterns = {
            QueryType.COMPARATIVE: [
                r"compare .* and .*",
                r"difference between .* and .*",
                r".*versus.*",
                r"pros and cons of.*",
                r"advantages and disadvantages.*"
            ],
            QueryType.TEMPORAL: [
                r"when did.*",
                r".*timeline.*",
                r".*chronological.*",
                r"before.*after.*",
                r"history of.*"
            ],
            QueryType.CAUSAL: [
                r"why does.*",
                r"what causes.*",
                r".*because.*",
                r".*leads to.*",
                r".*results in.*"
            ],
            QueryType.PROCEDURAL: [
                r"how to.*",
                r"steps to.*",
                r".*process.*",
                r".*procedure.*",
                r".*method.*"
            ],
            QueryType.ANALYTICAL: [
                r"analyze.*",
                r"evaluate.*",
                r"assess.*",
                r"examine.*",
                r".*implications.*"
            ]
        }
        
        logger.info("Initialized intelligent query planner")
    
    async def analyze_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> QueryType:
        """Analyze a query string to determine its semantic type.

        Uses regex pattern matching and heuristics to classify the query.

        Args:
            query (str): The user's input query string.
            context (Optional[Dict[str, Any]]): Additional context (e.g., conversation history).

        Returns:
            QueryType: The detected classification of the query.
        """
        try:
            query_lower = query.lower()
            
            # Check patterns for each query type
            for query_type, patterns in self.query_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, query_lower):
                        logger.info(f"Detected query type: {query_type} for query: {query[:50]}...")
                        return query_type
            
            # Additional heuristics
            if self._contains_multiple_questions(query):
                return QueryType.COMPLEX
            
            if self._spans_multiple_domains(query, context):
                return QueryType.MULTI_DOMAIN
            
            # Default to simple query
            return QueryType.SIMPLE
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return QueryType.SIMPLE
    
    async def create_query_plan(
        self, 
        query: str, 
        query_type: Optional[QueryType] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> QueryPlan:
        """Generate a comprehensive execution plan for the given query.

        This is the core planning method that orchestrates the decomposition and
        strategy selection process.

        Args:
            query (str): The original query text.
            query_type (Optional[QueryType]): Force a specific query type override.
            user_preferences (Optional[Dict[str, Any]]): User settings affecting planning.

        Returns:
            QueryPlan: A fully constructed query plan ready for execution.

        Raises:
            RAGError: If plan creation fails due to internal errors.
        """
        try:
            # Detect query type if not provided
            if query_type is None:
                query_type = await self.analyze_query(query, user_preferences)
            
            logger.info(f"Creating query plan for {query_type} query")
            
            # Determine strategy based on query type
            strategy = self._determine_strategy(query_type, query)
            
            # Generate sub-queries based on strategy
            sub_queries = await self._generate_sub_queries(query, query_type, strategy)
            
            # Create execution order considering dependencies
            execution_order = self._create_execution_order(sub_queries)
            
            # Estimate complexity and duration
            complexity = self._estimate_complexity(sub_queries)
            duration = self._estimate_duration(sub_queries, strategy)
            
            plan = QueryPlan(
                plan_id=f"plan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                original_query=query,
                query_type=query_type,
                strategy=strategy,
                sub_queries=sub_queries,
                execution_order=execution_order,
                estimated_complexity=complexity,
                estimated_duration_seconds=duration,
                metadata={
                    "created_at": datetime.utcnow().isoformat(),
                    "user_preferences": user_preferences or {},
                    "planner_version": "1.0"
                }
            )
            
            logger.info(
                f"Created query plan {plan.plan_id} with {len(sub_queries)} sub-queries, "
                f"complexity: {complexity:.2f}, estimated duration: {duration:.1f}s"
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Query plan creation failed: {e}")
            raise RAGError(f"Query planning failed: {e}")
    
    async def execute_query_plan(
        self,
        plan: QueryPlan,
        vector_store_service,
        llm_service,
        context: Optional[Dict[str, Any]] = None
    ) -> QueryExecution:
        """Execute a generated query plan.

        Orchestrates the execution of sub-queries, handling dependencies and
        aggregating results.

        Args:
            plan (QueryPlan): The plan to execute.
            vector_store_service: Service for retrieving documents.
            llm_service: Service for generating text/answers.
            context (Optional[Dict[str, Any]]): Execution context (e.g., user_id).

        Returns:
            QueryExecution: The final execution state containing all results.

        Raises:
            RAGError: If execution fails critically.
        """
        try:
            logger.info(f"Starting execution of query plan {plan.plan_id}")
            
            execution = QueryExecution(
                plan_id=plan.plan_id,
                status="running",
                current_step=0,
                completed_sub_queries=[],
                results={},
                start_time=datetime.utcnow(),
                end_time=None,
                total_chunks_retrieved=0,
                error_message=None
            )
            
            try:
                # Execute sub-queries in planned order
                for step, sub_query_id in enumerate(plan.execution_order):
                    execution.current_step = step
                    
                    sub_query = next(sq for sq in plan.sub_queries if sq.id == sub_query_id)
                    
                    logger.info(f"Executing sub-query {step + 1}/{len(plan.execution_order)}: {sub_query.text}")
                    
                    # Check dependencies
                    if not self._check_dependencies(sub_query, execution.completed_sub_queries):
                        raise RAGError(f"Dependencies not met for sub-query {sub_query_id}")
                    
                    # Execute the sub-query
                    result = await self._execute_sub_query(
                        sub_query, 
                        execution.results, 
                        vector_store_service, 
                        llm_service,
                        context
                    )
                    
                    execution.results[sub_query_id] = result
                    execution.completed_sub_queries.append(sub_query_id)
                    execution.total_chunks_retrieved += result.get("chunks_retrieved", 0)
                
                # Synthesize final result
                final_result = await self._synthesize_results(plan, execution.results)
                execution.results["final_synthesis"] = final_result
                
                execution.status = "completed"
                execution.end_time = datetime.utcnow()
                
                logger.info(
                    f"Completed query plan {plan.plan_id} in "
                    f"{(execution.end_time - execution.start_time).total_seconds():.1f}s"
                )
                
            except Exception as e:
                execution.status = "failed"
                execution.error_message = str(e)
                execution.end_time = datetime.utcnow()
                logger.error(f"Query plan execution failed: {e}")
                raise
            
            return execution
            
        except Exception as e:
            logger.error(f"Query plan execution failed: {e}")
            raise RAGError(f"Query execution failed: {e}")
    
    def _determine_strategy(self, query_type: QueryType, query: str) -> QueryStrategy:
        """Determine the best strategy for a query type."""
        strategy_map = {
            QueryType.SIMPLE: QueryStrategy.DIRECT,
            QueryType.COMPLEX: QueryStrategy.DECOMPOSED,
            QueryType.COMPARATIVE: QueryStrategy.DECOMPOSED,
            QueryType.TEMPORAL: QueryStrategy.HIERARCHICAL,
            QueryType.CAUSAL: QueryStrategy.ITERATIVE,
            QueryType.PROCEDURAL: QueryStrategy.HIERARCHICAL,
            QueryType.ANALYTICAL: QueryStrategy.DECOMPOSED,
            QueryType.MULTI_DOMAIN: QueryStrategy.EXPLORATORY
        }
        
        return strategy_map.get(query_type, QueryStrategy.DIRECT)
    
    async def _generate_sub_queries(
        self, 
        query: str, 
        query_type: QueryType, 
        strategy: QueryStrategy
    ) -> List[SubQuery]:
        """Generate sub-queries based on the main query and strategy."""
        sub_queries = []
        
        if strategy == QueryStrategy.DIRECT:
            # Simple query - no decomposition needed
            sub_queries.append(SubQuery(
                id="main",
                text=query,
                query_type=query_type,
                priority=1,
                depends_on=[],
                expected_result_type="direct_answer",
                metadata={}
            ))
        
        elif strategy == QueryStrategy.DECOMPOSED:
            # Break down complex query
            if query_type == QueryType.COMPARATIVE:
                sub_queries.extend(self._create_comparative_sub_queries(query))
            elif query_type == QueryType.ANALYTICAL:
                sub_queries.extend(self._create_analytical_sub_queries(query))
            else:
                sub_queries.extend(self._create_general_sub_queries(query))
        
        elif strategy == QueryStrategy.HIERARCHICAL:
            # Top-down approach
            sub_queries.extend(self._create_hierarchical_sub_queries(query, query_type))
        
        elif strategy == QueryStrategy.ITERATIVE:
            # Iterative refinement
            sub_queries.extend(self._create_iterative_sub_queries(query))
        
        elif strategy == QueryStrategy.EXPLORATORY:
            # Broad then narrow
            sub_queries.extend(self._create_exploratory_sub_queries(query))
        
        # Limit number of sub-queries
        return sub_queries[:self.max_sub_queries]
    
    def _create_comparative_sub_queries(self, query: str) -> List[SubQuery]:
        """Create sub-queries for comparative analysis."""
        # Extract entities to compare (simplified approach)
        entities = self._extract_entities_from_query(query)
        
        sub_queries = []
        
        # Query for each entity
        for i, entity in enumerate(entities[:3]):  # Limit to 3 entities
            sub_queries.append(SubQuery(
                id=f"entity_{i}",
                text=f"Information about {entity}",
                query_type=QueryType.SIMPLE,
                priority=1,
                depends_on=[],
                expected_result_type="entity_info",
                metadata={"entity": entity}
            ))
        
        # Comparison synthesis
        if len(entities) >= 2:
            sub_queries.append(SubQuery(
                id="comparison",
                text=f"Compare {entities[0]} and {entities[1]}",
                query_type=QueryType.COMPARATIVE,
                priority=2,
                depends_on=[f"entity_{i}" for i in range(min(len(entities), 3))],
                expected_result_type="comparison",
                metadata={"entities": entities[:3]}
            ))
        
        return sub_queries
    
    def _create_analytical_sub_queries(self, query: str) -> List[SubQuery]:
        """Create sub-queries for analytical queries."""
        sub_queries = []
        
        # Background information
        sub_queries.append(SubQuery(
            id="background",
            text=f"Background information for: {query}",
            query_type=QueryType.SIMPLE,
            priority=1,
            depends_on=[],
            expected_result_type="background",
            metadata={}
        ))
        
        # Specific analysis
        sub_queries.append(SubQuery(
            id="analysis",
            text=query,
            query_type=QueryType.ANALYTICAL,
            priority=2,
            depends_on=["background"],
            expected_result_type="analysis",
            metadata={}
        ))
        
        # Implications/conclusions
        sub_queries.append(SubQuery(
            id="implications",
            text=f"Implications and conclusions from: {query}",
            query_type=QueryType.ANALYTICAL,
            priority=3,
            depends_on=["analysis"],
            expected_result_type="conclusions",
            metadata={}
        ))
        
        return sub_queries
    
    def _create_general_sub_queries(self, query: str) -> List[SubQuery]:
        """Create general sub-queries for complex queries."""
        # Simple decomposition - split on conjunctions
        parts = re.split(r'\s+and\s+|\s+or\s+|\s*,\s*', query, maxsplit=3)
        
        sub_queries = []
        for i, part in enumerate(parts):
            if part.strip():
                sub_queries.append(SubQuery(
                    id=f"part_{i}",
                    text=part.strip(),
                    query_type=QueryType.SIMPLE,
                    priority=1,
                    depends_on=[],
                    expected_result_type="partial_answer",
                    metadata={"part_index": i}
                ))
        
        # Synthesis step if multiple parts
        if len(sub_queries) > 1:
            sub_queries.append(SubQuery(
                id="synthesis",
                text=f"Synthesize information about: {query}",
                query_type=QueryType.COMPLEX,
                priority=2,
                depends_on=[sq.id for sq in sub_queries],
                expected_result_type="synthesis",
                metadata={}
            ))
        
        return sub_queries
    
    def _create_hierarchical_sub_queries(self, query: str, query_type: QueryType) -> List[SubQuery]:
        """Create hierarchical sub-queries."""
        sub_queries = []
        
        # High-level overview
        sub_queries.append(SubQuery(
            id="overview",
            text=f"Overview of: {query}",
            query_type=QueryType.SIMPLE,
            priority=1,
            depends_on=[],
            expected_result_type="overview",
            metadata={}
        ))
        
        # Detailed information
        sub_queries.append(SubQuery(
            id="details",
            text=f"Detailed information about: {query}",
            query_type=query_type,
            priority=2,
            depends_on=["overview"],
            expected_result_type="details",
            metadata={}
        ))
        
        return sub_queries
    
    def _create_iterative_sub_queries(self, query: str) -> List[SubQuery]:
        """Create iterative refinement sub-queries."""
        sub_queries = []
        
        # Initial broad search
        sub_queries.append(SubQuery(
            id="initial",
            text=query,
            query_type=QueryType.SIMPLE,
            priority=1,
            depends_on=[],
            expected_result_type="initial_results",
            metadata={}
        ))
        
        # Refined search (will be determined based on initial results)
        sub_queries.append(SubQuery(
            id="refined",
            text=f"Refined search based on initial results for: {query}",
            query_type=QueryType.SIMPLE,
            priority=2,
            depends_on=["initial"],
            expected_result_type="refined_results",
            metadata={}
        ))
        
        return sub_queries
    
    def _create_exploratory_sub_queries(self, query: str) -> List[SubQuery]:
        """Create exploratory sub-queries for multi-domain queries."""
        sub_queries = []
        
        # Broad exploration
        sub_queries.append(SubQuery(
            id="exploration",
            text=f"Explore all aspects of: {query}",
            query_type=QueryType.SIMPLE,
            priority=1,
            depends_on=[],
            expected_result_type="exploration",
            metadata={}
        ))
        
        # Focused analysis
        sub_queries.append(SubQuery(
            id="focused",
            text=f"Focused analysis of: {query}",
            query_type=QueryType.ANALYTICAL,
            priority=2,
            depends_on=["exploration"],
            expected_result_type="focused_analysis",
            metadata={}
        ))
        
        return sub_queries
    
    def _create_execution_order(self, sub_queries: List[SubQuery]) -> List[str]:
        """Create execution order considering dependencies."""
        ordered = []
        processed = set()
        
        # Topological sort based on dependencies
        while len(ordered) < len(sub_queries):
            for sub_query in sub_queries:
                if sub_query.id not in processed:
                    # Check if all dependencies are satisfied
                    deps_satisfied = all(dep in processed for dep in sub_query.depends_on)
                    
                    if deps_satisfied:
                        ordered.append(sub_query.id)
                        processed.add(sub_query.id)
                        break
            else:
                # No progress made - circular dependency or error
                remaining = [sq.id for sq in sub_queries if sq.id not in processed]
                logger.warning(f"Circular dependency detected in sub-queries: {remaining}")
                ordered.extend(remaining)
                break
        
        return ordered
    
    def _estimate_complexity(self, sub_queries: List[SubQuery]) -> float:
        """Estimate query complexity."""
        base_complexity = len(sub_queries) * 0.1
        
        # Add complexity based on query types
        type_complexity = {
            QueryType.SIMPLE: 0.1,
            QueryType.COMPLEX: 0.3,
            QueryType.COMPARATIVE: 0.4,
            QueryType.ANALYTICAL: 0.5,
            QueryType.TEMPORAL: 0.3,
            QueryType.CAUSAL: 0.4,
            QueryType.PROCEDURAL: 0.3,
            QueryType.MULTI_DOMAIN: 0.6
        }
        
        for sub_query in sub_queries:
            base_complexity += type_complexity.get(sub_query.query_type, 0.2)
        
        return min(base_complexity, self.max_complexity)
    
    def _estimate_duration(self, sub_queries: List[SubQuery], strategy: QueryStrategy) -> float:
        """Estimate execution duration in seconds."""
        base_time = len(sub_queries) * 2.0  # 2 seconds per sub-query
        
        # Strategy modifiers
        strategy_modifiers = {
            QueryStrategy.DIRECT: 1.0,
            QueryStrategy.DECOMPOSED: 1.2,
            QueryStrategy.ITERATIVE: 1.5,
            QueryStrategy.HIERARCHICAL: 1.1,
            QueryStrategy.EXPLORATORY: 1.3
        }
        
        return base_time * strategy_modifiers.get(strategy, 1.0)
    
    def _check_dependencies(self, sub_query: SubQuery, completed: List[str]) -> bool:
        """Check if all dependencies for a sub-query are satisfied."""
        return all(dep in completed for dep in sub_query.depends_on)
    
    async def _execute_sub_query(
        self,
        sub_query: SubQuery,
        previous_results: Dict[str, Any],
        vector_store_service,
        llm_service,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a single sub-query."""
        try:
            # Enhance sub-query with context from previous results
            enhanced_query = await self._enhance_query_with_context(
                sub_query, previous_results
            )
            
            # Perform vector search
            search_results = await vector_store_service.search(
                query=enhanced_query,
                top_k=5,
                user_id=context.get("user_id", "system") if context else "system"
            )
            
            chunks_retrieved = len(search_results.get("chunks", []))
            
            # Generate answer if LLM is available
            answer = None
            if llm_service and llm_service.is_available():
                answer = await llm_service.generate_text(
                    prompt=f"Based on the following context, answer: {enhanced_query}\n\nContext: {search_results.get('context', '')}",
                    max_tokens=200
                )
            
            return {
                "sub_query_id": sub_query.id,
                "enhanced_query": enhanced_query,
                "search_results": search_results,
                "answer": answer,
                "chunks_retrieved": chunks_retrieved,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sub-query execution failed for {sub_query.id}: {e}")
            return {
                "sub_query_id": sub_query.id,
                "error": str(e),
                "chunks_retrieved": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _enhance_query_with_context(
        self,
        sub_query: SubQuery,
        previous_results: Dict[str, Any]
    ) -> str:
        """Enhance sub-query with context from previous results."""
        enhanced_query = sub_query.text
        
        # Add context from dependencies
        for dep_id in sub_query.depends_on:
            if dep_id in previous_results:
                dep_result = previous_results[dep_id]
                if dep_result.get("answer"):
                    enhanced_query += f" (Context: {dep_result['answer'][:100]}...)"
        
        return enhanced_query
    
    async def _synthesize_results(
        self, 
        plan: QueryPlan, 
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize results from all sub-queries."""
        try:
            synthesis = {
                "plan_id": plan.plan_id,
                "original_query": plan.original_query,
                "strategy_used": plan.strategy,
                "total_sub_queries": len(plan.sub_queries),
                "successful_queries": len([r for r in results.values() if not r.get("error")]),
                "total_chunks": sum(r.get("chunks_retrieved", 0) for r in results.values()),
                "synthesis_method": "intelligent_planning"
            }
            
            # Combine answers from successful sub-queries
            answers = []
            for sub_query in plan.sub_queries:
                result = results.get(sub_query.id, {})
                if result.get("answer") and not result.get("error"):
                    answers.append(f"{sub_query.text}: {result['answer']}")
            
            if answers:
                synthesis["combined_answer"] = " | ".join(answers)
            else:
                synthesis["combined_answer"] = "No successful results to synthesize."
            
            return synthesis
            
        except Exception as e:
            logger.error(f"Result synthesis failed: {e}")
            return {
                "error": f"Synthesis failed: {e}",
                "plan_id": plan.plan_id
            }
    
    def _extract_entities_from_query(self, query: str) -> List[str]:
        """Extract entities from a query (simplified approach)."""
        # Simple entity extraction - in production, use NER models
        words = query.split()
        entities = []
        
        # Look for capitalized words (potential entities)
        for word in words:
            if word[0].isupper() and len(word) > 2 and word not in ["What", "When", "Where", "How", "Why"]:
                entities.append(word)
        
        # Also extract quoted phrases
        quoted = re.findall(r'"([^"]*)"', query)
        entities.extend(quoted)
        
        return list(set(entities))[:5]  # Limit to 5 entities
    
    def _contains_multiple_questions(self, query: str) -> bool:
        """Check if query contains multiple questions."""
        question_markers = ["?", "what", "when", "where", "how", "why", "who"]
        question_count = sum(1 for marker in question_markers if marker in query.lower())
        return question_count > 1
    
    def _spans_multiple_domains(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if query spans multiple knowledge domains."""
        # Simple domain detection based on keywords
        domain_keywords = {
            "science": ["research", "study", "experiment", "hypothesis", "theory"],
            "technology": ["software", "hardware", "computer", "algorithm", "system"],
            "business": ["company", "market", "profit", "revenue", "strategy"],
            "health": ["medicine", "treatment", "disease", "patient", "medical"],
            "education": ["school", "student", "teacher", "learning", "curriculum"]
        }
        
        query_lower = query.lower()
        domains_found = []
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                domains_found.append(domain)
        
        return len(domains_found) > 1