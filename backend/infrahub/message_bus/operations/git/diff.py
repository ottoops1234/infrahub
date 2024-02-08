from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_diff_namesonly import GitDiffNamesOnlyResponse, GitDiffNamesOnlyResponseData
from infrahub.services import InfrahubServices

log = get_logger()


async def names_only(message: messages.GitDiffNamesOnly, service: InfrahubServices) -> None:
    log.info(
        "Collecting modifications between commits",
        repository=message.repository_name,
        repository_id=message.repository_id,
        repository_kind=message.repository_kind,
        first_commit=message.first_commit,
        second_commit=message.second_commit,
    )

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    files_changed, files_added, files_removed = await repo.calculate_diff_between_commits(
        first_commit=message.first_commit, second_commit=message.second_commit
    )

    if message.reply_requested:
        response = GitDiffNamesOnlyResponse(
            response_data=GitDiffNamesOnlyResponseData(
                files_added=files_added, files_changed=files_changed, files_removed=files_removed
            ),
        )
        await service.reply(message=response, initiator=message)
