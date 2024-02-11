import { Duration, Stack } from "aws-cdk-lib";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Rule, Schedule } from "aws-cdk-lib/aws-events";
import { LambdaFunction } from "aws-cdk-lib/aws-events-targets";
import { ManagedPolicy, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { DockerImageCode, DockerImageFunction } from "aws-cdk-lib/aws-lambda";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface MothershipStackProps {}

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

    const twilioToPhoneNumber = Secret.fromSecretCompleteArn(
      this,
      "TwilioToPhoneNumber",
      "arn:aws:secretsmanager:us-east-2:735029168602:secret:TwilioToPhoneNumber731680FF-AM1vinMMeROe-fk6Dmg"
    );

    const eventsTable = new Table(this, `MothershipEventsTable`, {
      tableName: "MothershipEventsTable",
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: {
        name: "Hash",
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
    twilioToPhoneNumber.grantRead(lambdaRole);

    const func = new DockerImageFunction(this, `MothershipLambdaFunction`, {
      code: code,
      role: lambdaRole,
      retryAttempts: 0,
      timeout: Duration.minutes(10),
      memorySize: 2048,
      environment: {
        PYTHONPATH: "/var/runtime:/opt",
        EVENTS_TABLE_NAME: eventsTable.tableName,
        TWILIO_ACCOUNT_SID_SECRET_NAME: twilioAuthSid.secretName,
        TWILIO_AUTH_TOKEN_SECRET_NAME: twilioAuthToken.secretName,
        TWILIO_FROM_PHONE_NUMBER_SECRET_NAME: twilioFromPhoneNumber.secretName,
        TWILIO_TO_PHONE_NUMBER_SECRET_NAME: twilioToPhoneNumber.secretName,
      },
    });

    // Create a CloudWatch Events rule to trigger the Lambda function every 10 minutes
    const rule = new Rule(this, "RunEveryTenMinutesRule", {
      schedule: Schedule.rate(Duration.minutes(10)),
    });

    // Add the Lambda function as a target of the CloudWatch Events rule
    rule.addTarget(new LambdaFunction(func));
  }
}
