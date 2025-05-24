from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import Toolkit
from agno.utils.log import logger

# Financials specific stats logic functions
from ..api_tools.contracts_data import (
    fetch_contracts_data_logic,
    get_player_contract as get_player_contract_logic, # Alias to avoid conflict
    get_team_payroll as get_team_payroll_logic,       # Alias
    get_highest_paid_players as get_highest_paid_players_logic, # Alias
    search_player_contracts as search_player_contracts_logic # Alias
)
from ..api_tools.free_agents_data import (
    fetch_free_agents_data_logic,
    get_free_agent_info as get_free_agent_info_logic, # Alias
    get_team_free_agents as get_team_free_agents_logic, # Alias
    get_top_free_agents as get_top_free_agents_logic,   # Alias
    search_free_agents as search_free_agents_logic   # Alias
)

class FinancialsToolkit(Toolkit):
    def __init__(self, **kwargs):
        tools = [
            self.get_contracts_data,
            self.get_player_contract_details,
            self.get_team_payroll_summary,
            self.get_highest_paid_players_list,
            self.search_player_contracts_by_name,
            self.get_free_agents_data,
            self.get_free_agent_player_info,
            self.get_team_former_free_agents,
            self.get_top_available_free_agents,
            self.search_free_agents_by_name,
        ]
        super().__init__(name="financials_toolkit", tools=tools, **kwargs)

    # --- Contract Data Tools ---

    def get_contracts_data(
        self,
        player_id: Optional[int] = None,
        team_id: Optional[int] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches NBA player contract data, with optional filtering by player ID or team ID.
        Data is sourced from a pre-cleaned CSV file.

        Args:
            player_id (Optional[int], optional): NBA API player ID to filter contracts for a specific player.
                                                 Defaults to None (no player filter).
            team_id (Optional[int], optional): NBA API team ID to filter contracts for a specific team.
                                               Defaults to None (no team filter).
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'contracts': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with contract data or an error message.
                    Expected success structure:
                    {{
                        "data_sets": {{
                            "contracts": [
                                {{
                                    "Player": str, "Team": str, "Age": int, "YOS": int, // Years of Service
                                    "Y1": Optional[float], ..., "Y8": Optional[float], // Salary per year
                                    "Signed Using": Optional[str], "Guaranteed": Optional[float],
                                    "Agent": Optional[str], "nba_player_id": Optional[float],
                                    "nba_team_id": Optional[float]
                                }}, ...
                            ]
                        }},
                        "parameters": {{"player_id": Optional[int], "team_id": Optional[int]}}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'contracts': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_contracts_data called with player_id: {player_id}, team_id: {team_id}")
        return fetch_contracts_data_logic(
            player_id=player_id,
            team_id=team_id,
            return_dataframe=return_dataframe
        )

    def get_player_contract_details(
        self,
        player_id: int,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Gets contract information for a specific player by their NBA API player ID.

        Args:
            player_id (int): NBA API player ID. This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'contracts': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with the player's contract data or an error.
                If return_dataframe=True: Tuple (json_string, {{'contracts': pd.DataFrame}}).
                    The DataFrame contains contract details for the specified player.
                    See `get_contracts_data` for the expected JSON structure of the contract list.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_player_contract_details called for player_id: {player_id}")
        return get_player_contract_logic( # Alias for fetch_contracts_data_logic with player_id
            player_id=player_id,
            return_dataframe=return_dataframe
        )

    def get_team_payroll_summary(
        self,
        team_id: int,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Gets payroll summary (list of player contracts) for a specific team by their NBA API team ID.

        Args:
            team_id (int): NBA API team ID. This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'contracts': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with the team's payroll data or an error.
                If return_dataframe=True: Tuple (json_string, {{'contracts': pd.DataFrame}}).
                    The DataFrame contains contract details for all players on the specified team.
                    See `get_contracts_data` for the expected JSON structure of the contract list.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_team_payroll_summary called for team_id: {team_id}")
        return get_team_payroll_logic( # Alias for fetch_contracts_data_logic with team_id
            team_id=team_id,
            return_dataframe=return_dataframe
        )

    def get_highest_paid_players_list(
        self,
        limit: int = 50,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Gets a list of the highest-paid players based on guaranteed money.

        Args:
            limit (int, optional): Maximum number of players to return. Defaults to 50.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'highest_paid_players': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with the list of highest-paid players or an error.
                    Expected success structure:
                    {{
                        "data_sets": {{
                            "highest_paid_players": [ {{ ... contract details for each player ... }} ]
                        }},
                        "parameters": {{"limit": int}}
                    }}
                    See `get_contracts_data` for the expected structure of individual contract details.
                If return_dataframe=True: Tuple (json_string, {{'highest_paid_players': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_highest_paid_players_list called with limit: {limit}")
        return get_highest_paid_players_logic(
            limit=limit,
            return_dataframe=return_dataframe
        )

    def search_player_contracts_by_name(
        self,
        player_name: str,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Searches for player contracts by player name (allows partial matches, case-insensitive).
        Results are sorted by guaranteed money in descending order.

        Args:
            player_name (str): Player name to search for. This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'player_contracts': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with matching player contracts or an error.
                    Expected success structure:
                    {{
                        "data_sets": {{
                            "player_contracts": [ {{ ... contract details for each matching player ... }} ]
                        }},
                        "parameters": {{"player_name": str}}
                    }}
                    See `get_contracts_data` for the expected structure of individual contract details.
                If return_dataframe=True: Tuple (json_string, {{'player_contracts': pd.DataFrame}}).
        """
        logger.info(f"FinancialsToolkit: search_player_contracts_by_name called for player: '{player_name}'")
        return search_player_contracts_logic(
            player_name=player_name,
            return_dataframe=return_dataframe
        )

    # --- Free Agent Data Tools ---

    def get_free_agents_data(
        self,
        player_id: Optional[int] = None,
        team_id: Optional[int] = None, # Represents the player's old team ID
        position: Optional[str] = None,
        free_agent_type: Optional[str] = None, # e.g., "ufa" (Unrestricted), "rfa" (Restricted)
        min_ppg: Optional[float] = None,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Fetches NBA free agent data with optional filtering.
        Data is sourced from a pre-cleaned CSV file.

        Args:
            player_id (Optional[int], optional): NBA API player ID to filter for a specific free agent. Defaults to None.
            team_id (Optional[int], optional): NBA API ID of the player's previous team to filter by. Defaults to None.
            position (Optional[str], optional): Player position to filter by (e.g., "G", "F", "C", "F-C"). Case-insensitive. Defaults to None.
            free_agent_type (Optional[str], optional): Type of free agent to filter by (e.g., "ufa", "rfa"). Defaults to None.
            min_ppg (Optional[float], optional): Minimum Points Per Game (PPG) to filter by. Defaults to None.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'free_agents': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with free agent data or an error message.
                    Expected success structure:
                    {{
                        "data_sets": {{
                            "free_agents": [
                                {{
                                    "playerDisplayName": str, "position": str, "type": str, // ufa/rfa
                                    "old_team": str, "PPG": Optional[float], "RPG": Optional[float], "APG": Optional[float],
                                    "nba_player_id": Optional[float], "nba_old_team_id": Optional[float]
                                }}, ...
                            ]
                        }},
                        "parameters": {{... applied filters ...}}
                    }}
                If return_dataframe=True: Tuple (json_string, {{'free_agents': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_free_agents_data called with player_id: {player_id}, team_id: {team_id}, position: {position}, type: {free_agent_type}, min_ppg: {min_ppg}")
        return fetch_free_agents_data_logic(
            player_id=player_id,
            team_id=team_id,
            position=position,
            free_agent_type=free_agent_type,
            min_ppg=min_ppg,
            return_dataframe=return_dataframe
        )

    def get_free_agent_player_info(
        self,
        player_id: int,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Gets free agent information for a specific player by their NBA API player ID.

        Args:
            player_id (int): NBA API player ID. This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'free_agents': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with the player's free agent data or an error.
                If return_dataframe=True: Tuple (json_string, {{'free_agents': pd.DataFrame}}).
                    The DataFrame contains free agent details for the specified player.
                    See `get_free_agents_data` for the expected JSON structure of the free agent list.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_free_agent_player_info called for player_id: {player_id}")
        return get_free_agent_info_logic( # Alias for fetch_free_agents_data_logic with player_id
            player_id=player_id,
            return_dataframe=return_dataframe
        )

    def get_team_former_free_agents(
        self,
        team_id: int,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Gets all free agents who previously played for a specific team, identified by NBA API team ID.

        Args:
            team_id (int): NBA API team ID. This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'free_agents': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with the list of former free agents for the team or an error.
                If return_dataframe=True: Tuple (json_string, {{'free_agents': pd.DataFrame}}).
                    The DataFrame contains details of free agents previously on the specified team.
                    See `get_free_agents_data` for the expected JSON structure of the free agent list.
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_team_former_free_agents called for team_id: {team_id}")
        return get_team_free_agents_logic( # Alias for fetch_free_agents_data_logic with team_id
            team_id=team_id,
            return_dataframe=return_dataframe
        )

    def get_top_available_free_agents(
        self,
        position: Optional[str] = None,
        free_agent_type: Optional[str] = None, # e.g., "ufa", "rfa"
        limit: int = 50,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Gets a list of top free agents, ranked by Points Per Game (PPG), with optional filters for position and free agent type.

        Args:
            position (Optional[str], optional): Player position to filter by (e.g., "G", "F", "C"). Case-insensitive. Defaults to None.
            free_agent_type (Optional[str], optional): Type of free agent ("ufa" or "rfa"). Defaults to None.
            limit (int, optional): Maximum number of free agents to return. Defaults to 50.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'top_free_agents': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with the list of top free agents or an error.
                    Expected success structure:
                    {{
                        "data_sets": {{
                            "top_free_agents": [ {{ ... free agent details for each player, sorted by PPG ... }} ]
                        }},
                        "parameters": {{... applied filters ...}}
                    }}
                    See `get_free_agents_data` for the expected structure of individual free agent details.
                If return_dataframe=True: Tuple (json_string, {{'top_free_agents': pd.DataFrame}}).
                    CSV cache path included in json_string under 'dataframe_info'.
        """
        logger.info(f"FinancialsToolkit: get_top_available_free_agents called with position: {position}, type: {free_agent_type}, limit: {limit}")
        return get_top_free_agents_logic(
            position=position,
            free_agent_type=free_agent_type,
            limit=limit,
            return_dataframe=return_dataframe
        )

    def search_free_agents_by_name(
        self,
        player_name: str,
        return_dataframe: bool = False
    ) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
        """
        Searches for free agents by player name (allows partial matches, case-insensitive).
        Results are sorted by Points Per Game (PPG) in descending order.

        Args:
            player_name (str): Player name to search for. This is required.
            return_dataframe (bool, optional): If True, returns a tuple (JSON response, {{'free_agent_search': DataFrame}}).
                                               Defaults to False.

        Returns:
            Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
                If return_dataframe=False: JSON string with matching free agents or an error.
                    Expected success structure:
                    {{
                        "data_sets": {{
                            "free_agent_search": [ {{ ... free agent details for each matching player ... }} ]
                        }},
                        "parameters": {{"player_name": str}}
                    }}
                    See `get_free_agents_data` for the expected structure of individual free agent details.
                If return_dataframe=True: Tuple (json_string, {{'free_agent_search': pd.DataFrame}}).
        """
        logger.info(f"FinancialsToolkit: search_free_agents_by_name called for player: '{player_name}'")
        return search_free_agents_logic(
            player_name=player_name,
            return_dataframe=return_dataframe
        )