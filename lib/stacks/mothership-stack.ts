import { Duration, Stack, StackProps } from "aws-cdk-lib";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Rule, Schedule } from "aws-cdk-lib/aws-events";
import { SfnStateMachine } from "aws-cdk-lib/aws-events-targets";
import { ManagedPolicy, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { DockerImageCode, DockerImageFunction } from "aws-cdk-lib/aws-lambda";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";
import {
  Choice,
  Condition,
  JsonPath,
  Map,
  Pass,
  StateMachine,
} from "aws-cdk-lib/aws-stepfunctions";
import {
  CallAwsService,
  LambdaInvoke,
} from "aws-cdk-lib/aws-stepfunctions-tasks";
import { Construct } from "constructs";

export interface MothershipStackProps extends StackProps {}

export class MothershipStack extends Stack {
  constructor(scope: Construct, id: string, props?: MothershipStackProps) {
    super(scope, id, props);

    // These secrets are already in my account from another
    // project
    const twilioAuthSid = Secret.fromSecretCompleteArn(
      this,
      "TwilioSidToken",
      "arn:aws:secretsmanager:us-east-2:735029168602:secret:TwilioAccountSID214470F8-hhba1UW1bVHD-v7KEQw"
    );

    const twilioAuthToken = Secret.fromSecretCompleteArn(
      this,
      "TwilioAuthToken",
      "arn:aws:secretsmanager:us-east-2:735029168602:secret:TwilioAuthTokenF995AA06-d2Y5Ib5bCnox-l9j9TB"
    );

    const twilioFromPhoneNumber = Secret.fromSecretCompleteArn(
      this,
      "TwilioFromPhoneNumber",
      "arn:aws:secretsmanager:us-east-2:735029168602:secret:TwilioFromPhoneNumberCF824E-m9GwC79fbcD7-MFd20Q"
    );

    const eventsTable = new Table(this, `MothershipEventsTable`, {
      tableName: "MothershipEventsTable",
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: {
        name: "Hash",
        type: AttributeType.STRING,
      },
    });

    const phoneNumbersTable = new Table(this, `MothershipPhoneNumbersTable`, {
      tableName: "MothershipPhoneNumbersTable",
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: {
        name: "PhoneNumber",
        type: AttributeType.STRING,
      },
    });

    const code = DockerImageCode.fromImageAsset("./", {});

    const lambdaRole = new Role(this, `MothershipLambdaFunctionRole`, {
      assumedBy: new ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    eventsTable.grantReadWriteData(lambdaRole);
    twilioAuthSid.grantRead(lambdaRole);
    twilioAuthToken.grantRead(lambdaRole);
    twilioFromPhoneNumber.grantRead(lambdaRole);

    const getNewMotherEventsFunction = new DockerImageFunction(
      this,
      `GetNewMothershipEventsFunction`,
      {
        code: code,
        role: lambdaRole,
        retryAttempts: 0,
        timeout: Duration.minutes(10),
        memorySize: 4096,
        environment: {
          HANDLER: "GET_NEW_MOTHERSHIP_EVENTS",
          PYTHONPATH: "/var/runtime:/opt",
          EVENTS_TABLE_NAME: eventsTable.tableName,
          TWILIO_ACCOUNT_SID_SECRET_NAME: twilioAuthSid.secretName,
          TWILIO_AUTH_TOKEN_SECRET_NAME: twilioAuthToken.secretName,
          TWILIO_FROM_PHONE_NUMBER_SECRET_NAME:
            twilioFromPhoneNumber.secretName,
        },
      }
    );

    const sendSmsMessageFunction = new DockerImageFunction(
      this,
      `SendSmsMessageFunction`,
      {
        code: code,
        role: lambdaRole,
        retryAttempts: 0,
        timeout: Duration.minutes(10),
        memorySize: 1024,
        environment: {
          HANDLER: "SEND_NOTIFICATION",
          PYTHONPATH: "/var/runtime:/opt",
          EVENTS_TABLE_NAME: eventsTable.tableName,
          TWILIO_ACCOUNT_SID_SECRET_NAME: twilioAuthSid.secretName,
          TWILIO_AUTH_TOKEN_SECRET_NAME: twilioAuthToken.secretName,
          TWILIO_FROM_PHONE_NUMBER_SECRET_NAME:
            twilioFromPhoneNumber.secretName,
        },
      }
    );

    const getNewMothershipEventsInvokeStep = new LambdaInvoke(
      this,
      "GetNewMothershipEventsStep",
      {
        lambdaFunction: getNewMotherEventsFunction,
        resultSelector: {
          events: JsonPath.stringAt("$.Payload"),
        },
      }
    );

    const sendSmsMessageInvokeStep = new LambdaInvoke(
      this,
      "SendSmsMessageStep",
      {
        lambdaFunction: sendSmsMessageFunction,
      }
    );

    const scanDdbTable = new CallAwsService(this, "ScanPhoneNumbersTableStep", {
      service: "dynamodb",
      action: "scan",
      parameters: {
        TableName: phoneNumbersTable.tableName,
      },
      iamResources: ["*"],
      resultPath: JsonPath.stringAt("$.result"),
    });

    const endPassState = new Pass(this, "EndPassState", {});

    // If there is at least one new event, go to the the workflow for sending SMS messages
    const choice = new Choice(this, "SendNotificationsChoice", {});
    const newEventsArePresentCondition = Condition.isPresent("$.events[0]");
    choice.when(newEventsArePresentCondition, scanDdbTable);
    choice.otherwise(endPassState);

    getNewMothershipEventsInvokeStep.next(choice);

    const mapState = new Map(this, "SendNotificationsMapState", {
      itemsPath: JsonPath.stringAt("$.result.Items"),
      parameters: {
        "phone_number.$": "$$.Map.Item.Value.PhoneNumber.S",
        "events.$": "$.events",
      },
    });
    mapState.iterator(sendSmsMessageInvokeStep);

    scanDdbTable.next(mapState);

    const stateMachine = new StateMachine(this, "MothershipStateMachine", {
      definition: getNewMothershipEventsInvokeStep,
    });

    // Create a CloudWatch Events rule to trigger the Lambda function every 5 minutes
    const rule = new Rule(this, "RunEveryFiveMinutesRule", {
      schedule: Schedule.rate(Duration.minutes(5)),
    });

    // Add the Lambda function as a target of the CloudWatch Events rule
    rule.addTarget(new SfnStateMachine(stateMachine));
  }
}
