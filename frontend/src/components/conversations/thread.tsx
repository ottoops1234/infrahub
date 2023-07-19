import { gql, useReactiveVar } from "@apollo/client";
import { useContext, useState } from "react";
import { toast } from "react-toastify";
import { PROPOSED_CHANGES_THREAD_COMMENT_OBJECT } from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import { stringifyWithoutQuotes } from "../../utils/string";
import { ALERT_TYPES, Alert } from "../alert";
import { Button } from "../button";
import { AddComment } from "./add-comment";
import { Comment } from "./comment";

type tThread = {
  thread: any;
  refetch: Function;
};

export const Thread = (props: tThread) => {
  const { thread, refetch } = props;

  const auth = useContext(AuthContext);
  console.log("auth: ", auth);

  const { comments } = thread;

  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);
  const [displayAddComment, setDisplayAddComment] = useState(false);

  const handleSubmit = async (data?: any) => {
    try {
      if (!data) {
        return;
      }

      const newObject = {
        text: {
          value: data.comment,
        },
        thread: {
          id: thread.id,
        },
        created_by: {
          id: auth,
        },
      };

      const mutationString = createObject({
        kind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: stringifyWithoutQuotes(newObject),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Comment added"} />);

      refetch();

      setIsLoading(false);
    } catch (error: any) {
      console.error("An error occured while creating the comment: ", error);

      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"An error occured while creating the comment"}
          details={error.message}
        />
      );

      setIsLoading(false);
    }
  };

  return (
    <section className="bg-custom-white p-4 mb-4 rounded-lg">
      <div className="">
        {comments.edges.map((comment: any, index: number) => (
          <Comment key={index} comment={comment.node} className={"border border-gray-200"} />
        ))}
      </div>

      <div className="flex justify-end">
        {displayAddComment && (
          <div className="flex-1">
            <AddComment
              onSubmit={handleSubmit}
              isLoading={isLoading}
              onClose={() => setDisplayAddComment(false)}
              disabled={auth?.permissions?.write}
            />
          </div>
        )}

        {!displayAddComment && (
          <Button onClick={() => setDisplayAddComment(true)} disabled={auth?.permissions?.write}>
            Reply
          </Button>
        )}
      </div>
    </section>
  );
};
