import { CfnOutput, Duration, Stack, StackProps } from "aws-cdk-lib";
import { LambdaRestApi } from "aws-cdk-lib/aws-apigateway";
import { AttributeType, BillingMode, StreamViewType, Table } from "aws-cdk-lib/aws-dynamodb";
import { ManagedPolicy, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { DockerImageCode, DockerImageFunction, StartingPosition } from "aws-cdk-lib/aws-lambda";
import { DynamoEventSource } from "aws-cdk-lib/aws-lambda-event-sources";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export type MothershipStackProps = StackProps;

export class MothershipStack extends Stack {
  constructor(scope: Construct, id: string, props?: MothershipStackProps) {
    super(scope, id, props);

    const discordBotToken = Secret.fromSecretNameV2(
      this,
      "DiscordBotToken",
      "mothership/discord-bot-token"
    );

    const discordPublicKeySecret = Secret.fromSecretNameV2(
      this,
      "DiscordPublicKeySecret",
      "mothership/discord-public-key"
    );

    const eventsTable = new Table(this, "MothershipEventsTable", {
      tableName: "MothershipEventsTable",
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: "Hash", type: AttributeType.STRING },
      stream: StreamViewType.NEW_IMAGE,
    });

    const filteredTitlesTable = new Table(this, "MothershipFilteredTitlesTable", {
      tableName: "MothershipFilteredTitlesTable",
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: "Title", type: AttributeType.STRING },
    });

    const code = DockerImageCode.fromImageAsset("./", {});

    const sendNotificationRole = new Role(this, "SendNotificationLambdaRole", {
      assumedBy: new ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole"),
      ],
    });
    discordBotToken.grantRead(sendNotificationRole);
    filteredTitlesTable.grantReadData(sendNotificationRole);

    const interactionRole = new Role(this, "InteractionLambdaRole", {
      assumedBy: new ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole"),
      ],
    });
    filteredTitlesTable.grantReadWriteData(interactionRole);
    discordPublicKeySecret.grantRead(interactionRole);

    const discordChannelId = "1508354117398171678";

    const sendNotificationFunction = new DockerImageFunction(this, "SendNotificationFunction", {
      code,
      role: sendNotificationRole,
      retryAttempts: 0,
      timeout: Duration.minutes(1),
      memorySize: 512,
      environment: {
        HANDLER: "SEND_NOTIFICATION",
        PYTHONPATH: "/var/runtime:/opt",
        DISCORD_BOT_TOKEN_SECRET_NAME: discordBotToken.secretName,
        DISCORD_CHANNEL_ID: discordChannelId,
        FILTERED_TITLES_TABLE_NAME: filteredTitlesTable.tableName,
      },
    });

    sendNotificationFunction.addEventSource(
      new DynamoEventSource(eventsTable, {
        startingPosition: StartingPosition.LATEST,
        batchSize: 10,
        bisectBatchOnError: true,
        retryAttempts: 2,
      })
    );

    const interactionFunction = new DockerImageFunction(this, "DiscordInteractionFunction", {
      code,
      role: interactionRole,
      retryAttempts: 0,
      timeout: Duration.seconds(29),
      memorySize: 256,
      environment: {
        HANDLER: "HANDLE_DISCORD_INTERACTION",
        PYTHONPATH: "/var/runtime:/opt",
        DISCORD_PUBLIC_KEY_SECRET_NAME: discordPublicKeySecret.secretName,
        FILTERED_TITLES_TABLE_NAME: filteredTitlesTable.tableName,
      },
    });

    const interactionApi = new LambdaRestApi(this, "DiscordInteractionApi", {
      handler: interactionFunction,
      proxy: true,
      deployOptions: { stageName: "prod" },
    });

    new CfnOutput(this, "InteractionEndpointUrl", {
      value: interactionApi.url,
      description: "Set this URL as the Interactions Endpoint URL in your Discord app settings",
    });
  }
}
