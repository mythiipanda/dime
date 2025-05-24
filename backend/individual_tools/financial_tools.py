from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# Financials specific stats logic functions
from ..api_tools.contracts_data import (
    fetch_contracts_data_logic,
    get_player_contract as get_player_contract_logic_alias,
    get_team_payroll as get_team_payroll_logic_alias,
    get_highest_paid_players as get_highest_paid_players_logic_alias,
    search_player_contracts as search_player_contracts_logic_alias
)
from ..api_tools.free_agents_data import (
    fetch_free_agents_data_logic,
    get_free_agent_info as get_free_agent_info_logic_alias,
    get_team_free_agents as get_team_free_agents_logic_alias,
    get_top_free_agents as get_top_free_agents_logic_alias,
    search_free_agents as search_free_agents_logic_alias
)

# --- Contract Data Tools ---

@tool
def get_contracts_data(
    player_id: Optional[int] = None,
    team_id: Optional[int] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA player contract data, optionally filtered by player ID or team ID.
    Args:
        player_id (Optional[int]): Player ID. Defaults to None.
        team_id (Optional[int]): Team ID. Defaults to None.
        return_dataframe (bool): If True, returns (JSON, {{'contracts': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_contracts_data called with player_id: {player_id}, team_id: {team_id}")
    return fetch_contracts_data_logic(
        player_id=player_id,
        team_id=team_id,
        return_dataframe=return_dataframe
    )

@tool
def get_player_contract_details(
    player_id: int,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets contract information for a specific player by their NBA API player ID.
    Args:
        player_id (int): NBA API player ID.
        return_dataframe (bool): If True, returns (JSON, {{'contracts': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_player_contract_details called for player_id: {player_id}")
    # This logic function is an alias in the original toolkit, directly calling it here.
    return get_player_contract_logic_alias(
        player_id=player_id,
        return_dataframe=return_dataframe
    )

@tool
def get_team_payroll_summary(
    team_id: int,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets payroll summary for a specific team by their NBA API team ID.
    Args:
        team_id (int): NBA API team ID.
        return_dataframe (bool): If True, returns (JSON, {{'contracts': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_payroll_summary called for team_id: {team_id}")
    return get_team_payroll_logic_alias(
        team_id=team_id,
        return_dataframe=return_dataframe
    )

@tool
def get_highest_paid_players_list(
    limit: int = 50,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets a list of the highest-paid players based on guaranteed money.
    Args:
        limit (int): Maximum number of players to return. Defaults to 50.
        return_dataframe (bool): If True, returns (JSON, {{'highest_paid_players': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_highest_paid_players_list called with limit: {limit}")
    return get_highest_paid_players_logic_alias(
        limit=limit,
        return_dataframe=return_dataframe
    )

@tool
def search_player_contracts_by_name(
    player_name: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Searches for player contracts by player name (allows partial matches).
    Args:
        player_name (str): Player name to search for.
        return_dataframe (bool): If True, returns (JSON, {{'player_contracts': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: search_player_contracts_by_name called for player: '{player_name}'")
    return search_player_contracts_logic_alias(
        player_name=player_name,
        return_dataframe=return_dataframe
    )

# --- Free Agent Data Tools ---

@tool
def get_free_agents_data(
    player_id: Optional[int] = None,
    team_id: Optional[int] = None, 
    position: Optional[str] = None,
    free_agent_type: Optional[str] = None,
    min_ppg: Optional[float] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA free agent data with optional filtering.
    Args:
        player_id (Optional[int]): Player ID. Defaults to None.
        team_id (Optional[int]): Player's old team ID. Defaults to None.
        position (Optional[str]): Player position (e.g., "G", "F"). Defaults to None.
        free_agent_type (Optional[str]): E.g., "ufa", "rfa". Defaults to None.
        min_ppg (Optional[float]): Minimum PPG. Defaults to None.
        return_dataframe (bool): If True, returns (JSON, {{'free_agents': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_free_agents_data with filters: player_id={player_id}, team_id={team_id}, pos={position}, type={free_agent_type}, min_ppg={min_ppg}")
    return fetch_free_agents_data_logic(
        player_id=player_id,
        team_id=team_id,
        position=position,
        free_agent_type=free_agent_type,
        min_ppg=min_ppg,
        return_dataframe=return_dataframe
    )

@tool
def get_free_agent_player_info(
    player_id: int,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets free agent information for a specific player by their NBA API player ID.
    Args:
        player_id (int): NBA API player ID.
        return_dataframe (bool): If True, returns (JSON, {{'free_agents': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_free_agent_player_info called for player_id: {player_id}")
    return get_free_agent_info_logic_alias(
        player_id=player_id,
        return_dataframe=return_dataframe
    )

@tool
def get_team_former_free_agents(
    team_id: int,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets free agents whose former team matches the given NBA API team ID.
    Args:
        team_id (int): NBA API ID of the player's previous team.
        return_dataframe (bool): If True, returns (JSON, {{'free_agents': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_former_free_agents called for team_id: {team_id}")
    return get_team_free_agents_logic_alias(
        team_id=team_id,
        return_dataframe=return_dataframe
    )

@tool
def get_top_available_free_agents(
    position: Optional[str] = None,
    free_agent_type: Optional[str] = None, 
    limit: int = 50,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Gets a list of top available free agents, optionally filtered and limited.
    Args:
        position (Optional[str]): Player position. Defaults to None.
        free_agent_type (Optional[str]): E.g., "ufa", "rfa". Defaults to None.
        limit (int): Maximum number of players to return. Defaults to 50.
        return_dataframe (bool): If True, returns (JSON, {{'top_free_agents': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_top_available_free_agents with pos={position}, type={free_agent_type}, limit={limit}")
    return get_top_free_agents_logic_alias(
        position=position,
        free_agent_type=free_agent_type,
        limit=limit,
        return_dataframe=return_dataframe
    )

@tool
def search_free_agents_by_name(
    player_name: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Searches for free agents by player name (allows partial matches).
    Args:
        player_name (str): Player name to search for.
        return_dataframe (bool): If True, returns (JSON, {{'matching_free_agents': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: search_free_agents_by_name called for player: '{player_name}'")
    return search_free_agents_logic_alias(
        player_name=player_name,
        return_dataframe=return_dataframe
    ) 