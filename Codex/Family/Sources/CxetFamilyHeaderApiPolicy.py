"""Reviewed API ownership within intentionally shared compiler include roots.

Physical visibility and identity remain checked by HeaderContract. These
closed file inventories assign semantic API owners without inventing CMake
usage requirements or treating every visible header as every target's API.
"""

from __future__ import annotations


_PARTITION_GROUPS = (
    ('apps/trading-core/src/Contracts/include/trading_core', 'trading_core_contracts', (
        'Contracts/Analytics/DeliveryEpisode.hpp',
        'Contracts/AttemptDisposition.hpp',
        'Contracts/IdentityTypes.hpp',
        'Contracts/Numeric/Integer/Bps.hpp',
        'Contracts/Numeric/Integer/PercentMove.hpp',
        'Contracts/Numeric/Integer/Ratio.hpp',
        'Contracts/Numeric/Integer/Saturating.hpp',
        'Contracts/Numeric/Integer/WideDivision.hpp',
        'Contracts/Numeric/PercentBps.hpp',
        'Contracts/Numeric/PriceQuantity/NotionalQty.hpp',
        'Contracts/Numeric/PriceQuantity/PriceNormalization.hpp',
        'Contracts/Numeric/PriceQuantity/QuantityGrid.hpp',
        'Contracts/Numeric/PriceQuantity/TickQuoteMath.hpp',
    )),
    ('apps/vetron/src/Gateway/include/vetron', 'vetron_read_gateway', (
        'Browser/Codec.hpp',
        'Gateway/Gateway.hpp',
        'Gateway/HistoryFocusWire.hpp',
        'Gateway/LoopbackServer.hpp',
        'Gateway/MarketViewDemandWire.hpp',
        'Gateway/StaticAssetStore.hpp',
        'Gateway/TypedControlEndpoint.hpp',
    )),
    ('apps/vetron/src/Gateway/include/vetron', 'vetron_full_control', (
        'Gateway/FullControlBridge.hpp',
        'Gateway/FullGateway.hpp',
        'Gateway/FullLoopbackServer.hpp',
    )),
    ('apps/vetron/src/Process/include/vetron', 'vetron_read_process', (
        'Process/Vetrond.hpp',
    )),
    ('apps/vetron/src/Process/include/vetron', 'vetron_full_process', (
        'Process/FullVetrond.hpp',
    )),
    ('apps/trading-core/src/Core/include/trading_core', 'trading_core_algorithm', (
        'Algorithm/Storage/RetainedStateSlots.hpp',
        'Algorithm/Math/PriceQuantity/PriceBasis.hpp',
        'Algorithm/AlgorithmCore.hpp',
        'Algorithm/Fees/FeePresets.hpp',
        'Algorithm/Fees/OrderCommission.hpp',
        'Algorithm/Fees/SpotFeeContract.hpp',
        'Algorithm/Indicators/BoundedGroupTopology.hpp',
        'Algorithm/Market/AggregatedOrderBook.hpp',
        'Algorithm/Market/BboReconstruction.hpp',
        'Algorithm/Market/LocalOrderBook.hpp',
        'Algorithm/Market/LocalOrderBookFreshness.ipp',
        'Algorithm/Market/LocalOrderBookLiquidity.ipp',
        'Algorithm/Market/LocalOrderBookStorage.ipp',
        'Algorithm/Market/LocalOrderBookUpdates.ipp',
        'Algorithm/Market/MarketTime.hpp',
        'Algorithm/Market/MarketView.hpp',
        'Algorithm/Market/PairMarketDirectionPolicy.hpp',
        'Algorithm/Market/StrategyInputs.hpp',
        'Algorithm/Signals/Alerts/AlertCondition.hpp',
        'Algorithm/Signals/Basis/CentralBankCarry.hpp',
        'Algorithm/Signals/Basis/DeliveryBasis.hpp',
        'Algorithm/Signals/Basis/DeliveryBasisDiagnostic.hpp',
        'Algorithm/Signals/Basis/DeliveryBasisMath.hpp',
        'Algorithm/Signals/Basis/DeliveryEpisode.hpp',
        'Algorithm/Signals/Basis/DeliveryPairBasis.hpp',
        'Algorithm/Signals/Basis/DeliveryReferenceModel.hpp',
        'Algorithm/Signals/Basis/DeliveryValuation.hpp',
        'Algorithm/Signals/Basis/DeliveryValuationReference.hpp',
        'Algorithm/Signals/Basis/DeliveryValuationSamples.hpp',
        'Algorithm/Signals/Basis/DeliveryValuationTypes.hpp',
        'Algorithm/Signals/Flow/DecayedTradeIntensity.hpp',
        'Algorithm/Signals/Flow/ToxicFlowScore.hpp',
        'Algorithm/Signals/Iceberg/ClassicIcebergDetector.hpp',
        'Algorithm/Signals/Iceberg/IcebergCommon.hpp',
        'Algorithm/Signals/Iceberg/IcebergDetector.hpp',
        'Algorithm/Signals/Iceberg/SmartIcebergDetector.hpp',
        'Algorithm/Signals/Liquidity/LiquidityWallDetector.hpp',
        'Algorithm/Signals/MeanReversion/PairMeanReversion.hpp',
        'Algorithm/Signals/MeanReversion/StatArbMakerMath.hpp',
        'Algorithm/Signals/Regime/CusumRegime.hpp',
        'Algorithm/Signals/Regression/RecursiveLeastSquares.hpp',
        'Algorithm/Signals/Statistics/RecursiveMoments.hpp',
        'Algorithm/Signals/Trades/RollingTradeNotional.hpp',
        'Algorithm/Signals/Trades/TradeRangeEma.hpp',
        'Algorithm/Signals/Trades/TradeTape.hpp',
        'Algorithm/Signals/Trades/TradeTapeHistory.hpp',
        'Algorithm/Signals/Trend/TrendScore.hpp',
        'Algorithm/Signals/Volatility/RelativeDifferenceVolatility.hpp',
        'Algorithm/Signals/Volatility/VolatilityBps.hpp',
        'Algorithm/Market/Bbo/SyntheticBboCalculation.hpp',
        'Algorithm/Market/Bbo/SyntheticBboState.hpp',
        'Algorithm/Market/Pairs/SyntheticPairSelection.hpp',
        'Algorithm/Market/Pairs/InstrumentEligibility.hpp',
        'Algorithm/Market/Pairs/SyntheticPairTopology.hpp',
        'Algorithm/Ranking/Index/SymbolIndex.hpp',
        'Algorithm/Ranking/Index/SpreadRows.hpp',
        'Algorithm/Ranking/Selection/RowSelection.hpp',
        'Algorithm/Ranking/Selection/RowOrder.hpp',
        'Algorithm/Ranking/Metrics/VolumeValues.hpp',
        'Algorithm/Ranking/Metrics/SpreadValue.hpp',
        'Algorithm/Signals/Volatility/SpreadVolatilityWorkspace.hpp',
        'Algorithm/Signals/Volatility/SpreadVolatilityTypes.hpp',
        'Algorithm/Signals/Volatility/Detail/SpreadVolatilityPublication.ipp',
        'Algorithm/Signals/Volatility/Detail/SpreadVolatilityUpdates.ipp',
        'Algorithm/Signals/Basis/Reference/DeliveryReference.hpp',
        'Algorithm/Signals/Basis/Ranking/DeliveryRankingEvidence.hpp',
    )),
    ('apps/trading-core/src/Core/include/trading_core', 'trading_core_headers', (
        'Algorithm/Math/Formula/Formula.hpp',
        'Algorithm/Math/Integer/BoundedExp.hpp',
        'Algorithm/Math/Integer/Exp2Decay.hpp',
        'Algorithm/Math/PriceQuantity/MarketMeasurements.hpp',
        'Algorithm/Math/PriceQuantity/PriceLimitDistance.hpp',
        'Algorithm/Math/Smoothing/ContinuousEma.hpp',
        'Algorithm/Math/Smoothing/Ewma.hpp',
        'Algorithm/Math/Smoothing/NotionalEma.hpp',
        'Algorithm/Math/Spread/FundingSpread.hpp',
        'Algorithm/Math/Spread/History.hpp',
        'Algorithm/Math/Spread/LiveBbo.hpp',
        'Algorithm/Math/Spread/QuoteConversion.hpp',
        'Algorithm/Math/Spread/QuoteConversionTypes.hpp',
        'Algorithm/Primitives/AlgorithmPrimitives.hpp',
        'Algorithm/Primitives/Crc32c.hpp',
        'Algorithm/Primitives/StreamDescriptor.hpp',
        'Algorithm/Primitives/SymbolShard.hpp',
        'Contracts/Control/ControlState.hpp',
        'Contracts/Intents/Intent.hpp',
        'Contracts/Intents/IntentValidation.hpp',
        'Contracts/Intents/OrderProblem.hpp',
        'Contracts/Intents/OrderState.hpp',
        'Contracts/Intents/PositionState.hpp',
        'Contracts/State/AccountState/RateLimitView.hpp',
        'Contracts/State/Orders/OrderAuthorityView.hpp',
        'Contracts/State/Orders/OrderEvidenceView.hpp',
        'Contracts/State/Orders/OrderPathWarmupState.hpp',
        'Contracts/State/Positions/PositionAuthorityView.hpp',
        'Contracts/Strategy/StrategyDecisionTrace.hpp',
        'Contracts/Strategy/StrategyExecutionTrace.hpp',
        'Contracts/Strategy/StrategyLegMarket.hpp',
        'Contracts/Supervision.hpp',
        'Strategy/Orders/Evidence/PairExecutionObservationTypes.hpp',
    )),
    ('apps/trading-core/src/Core/include/trading_core', 'trading_core_strategy', (
        'Strategy/Descriptor/StrategyRuntimeContract.hpp',
        'Strategy/Descriptor/StrategyRuntimeValues.hpp',
        'Strategy/Signal/StrategySignal.hpp',
        'Contracts/Core.hpp',
        'Contracts/Strategy/StrategyContract.hpp',
        'Strategy/Context/StrategyContextView.hpp',
        'Strategy/Descriptor/PairCatalogSelection.hpp',
        'Strategy/Descriptor/StrategyDescriptor.hpp',
        'Strategy/Descriptor/StrategyInstanceSelection.hpp',
        'Strategy/Descriptor/StrategyParamResolution.hpp',
        'Strategy/Descriptor/StrategyRuntimeFootprint.hpp',
        'Strategy/Descriptor/StrategyRuntimePolicy.hpp',
        'Strategy/Descriptor/StrategyTradeHistory.hpp',
        'Strategy/Events/UserEventView.hpp',
        'Strategy/Fill/MarketFillEvidence.hpp',
        'Strategy/Fill/SpeculativeDecisions.hpp',
        'Strategy/Fill/TransactionFillEvidence.hpp',
        'Strategy/Market/MarketDataTools.hpp',
        'Strategy/Market/OrderBookTools.hpp',
        'Strategy/Market/PairMarketPolicy.hpp',
        'Strategy/Market/SignalTools.hpp',
        'Strategy/Orders/Execution/CancelDecision.hpp',
        'Strategy/Orders/Intent/CloseIntents.hpp',
        'Strategy/Orders/Execution/ExecutionDecisions.hpp',
        'Strategy/Orders/Intent/IntentBuilders.hpp',
        'Strategy/Orders/Intent/IntentRollback.hpp',
        'Strategy/Orders/Evidence/OrderDecisionCursor.hpp',
        'Strategy/Orders/Execution/OrderDecisionRules.hpp',
        'Strategy/Orders/Admission/PairAdmission.hpp',
        'Strategy/Orders/Execution/PairExecution.hpp',
        'Strategy/Orders/Execution/PairExecutionPool.hpp',
        'Strategy/Orders/Execution/PairExecutionClosing.ipp',
        'Strategy/Orders/Execution/PairExecutionEvidence.ipp',
        'Strategy/Orders/Evidence/PairExecutionObservation.hpp',
        'Strategy/Orders/Execution/PairExecutionOpening.ipp',
        'Strategy/Orders/Admission/PairFunding.hpp',
        'Strategy/Orders/Execution/PairStrategyInputs.hpp',
        'Strategy/Orders/Execution/PairStrategyRuntimeState.hpp',
        'Strategy/Orders/Execution/PairedDecisions.hpp',
        'Strategy/Orders/Execution/QuoteDecision.hpp',
        'Strategy/Orders/Intent/QuoteIntentPolicy.hpp',
        'Strategy/Orders/Intent/ReactiveIntents.hpp',
        'Strategy/Orders/Evidence/RetiredIntentDecisions.hpp',
        'Strategy/Orders/Admission/StrategyCloseGrant.hpp',
        'Strategy/Orders/Execution/StrategyStopPolicy.hpp',
        'Strategy/Orders/Intent/WarmupIntents.hpp',
        'Strategy/Params/StrategyParams.hpp',
        'Strategy/Position/PositionPlanning.hpp',
        'Strategy/Risk/MakerQuotaPolicy.hpp',
        'Strategy/Risk/PairedRecovery.hpp',
        'Strategy/Risk/PortfolioRisk.hpp',
        'Strategy/Risk/PositionAdmission.hpp',
        'Strategy/Risk/ReduceOnlyPlanning.hpp',
        'Strategy/State/StrategyCheckpoint.hpp',
        'Strategy/State/StrategyCheckpointFields.hpp',
        'Strategy/State/StrategyStateArena.hpp',
        'Strategy/StrategyApi.hpp',
        'Strategy/StrategyInputFreshness.hpp',
        'Strategy/StrategyInstance.hpp',
        'Strategy/StrategyMarketData.hpp',
        'Strategy/StrategyTransactionTracker.hpp',
        'Strategy/StrategyTransactionValidation.hpp',
    )),
    ('apps/trading-core/src/Core/include/trading_core', 'trading_core_execution', (
        'Execution/EngineResult.hpp',
        'Execution/OrderNameValues.hpp',
        'Execution/OrderReconciliation.hpp',
        'Execution/OrderValues.hpp',
        'Execution/PermitTypes.hpp',
        'Execution/PreparedPermitPool.hpp',
        'Execution/QuotaPreview.hpp',
        'Execution/RecoveryCut.hpp',
        'Execution/ReplacementPolicy.hpp',
        'Execution/SharedAdmissionOwner.hpp',
        'Execution/SharedAdmissionTypes.hpp',
        'Contracts/State/AccountState/AccountState.hpp',
        'Contracts/State/StrategyStateView.hpp',
        'Execution/CapitalAdmission.ipp',
        'Execution/Engine.hpp',
        'Execution/EntryAdmissionQueue.hpp',
        'Execution/Identity.hpp',
        'Execution/OrderName.hpp',
        'Execution/Orders.hpp',
        'Execution/Permits.hpp',
        'Execution/Recovery.hpp',
        'Execution/SharedAccountAdmission.hpp',
        'Execution/SharedQuotaReservations.ipp',
    )),
    ('apps/trading-core/capital/include/capital', 'capital_finance', (
        'AccountState/AccountState.hpp',
        'AccountState/CapitalFunding.hpp',
        'Accounting/Account.hpp',
        'Accounting/AccountSnapshot.hpp',
        'Accounting/AssetFacts.hpp',
        'Accounting/FillPositionAccounting.hpp',
        'Accounting/PositionFacts.hpp',
        'Budget/CapitalBudget.hpp',
        'Budget/CapitalBudgetTypes.hpp',
        'Budget/CapitalRequirement.hpp',
        'Budget/EntryFunding.hpp',
        'Budget/SharedCapital.hpp',
        'Budget/SharedCapitalAccount.hpp',
        'Budget/SharedCapitalReservations.ipp',
        'Budget/SharedCapitalStorage.hpp',
        'Budget/SharedCapitalTypes.hpp',
        'Budget/SpotEpisode.hpp',
        'Budget/SpotEpisodeTypes.hpp',
        'Decision/PairSizingDecision.hpp',
        'Decision/PairSizingInput.hpp',
        'Decision/PairSizingWorkspace.hpp',
        'Decision/ThresholdSignal.hpp',
        'Finance.hpp',
        'FinancialTypes.hpp',
        'Risk/PairAssessment.hpp',
        'Risk/PortfolioRisk.hpp',
        'Risk/PositionExposure.ipp',
        'Risk/PositionRisk.hpp',
        'Risk/RiskNumerics.hpp',
        'Sizing/Detail/OrderSizingMath.hpp',
        'Sizing/Detail/OrdinaryPairQuantity.hpp',
        'Sizing/Detail/PairSizingMath.hpp',
        'Sizing/FundedPairSizing.hpp',
        'Sizing/OrderSizing.hpp',
        'Sizing/OrderSizingTypes.hpp',
        'Sizing/PairSizing.hpp',
        'Sizing/PairSizingTypes.hpp',
        'Sizing/PreparePairLotsSizing.hpp',
        'Sizing/PreparedPairSizing.hpp',
        'Sizing/PreparedPairSizingTypes.hpp',
        'Sizing/QuantityIntersection.hpp',
        'Sizing/SizingPolicy.hpp',
    )),
    ('apps/trading-core/capital/include/capital', 'capital_planning', (
        'Planning/AccountDp.hpp',
        'Planning/CapitalAllocationTypes.hpp',
        'Planning/Dp.hpp',
        'Planning/Market.hpp',
        'Planning/Graph.hpp',
    )),
    ('apps/hft-parser/src/Runtime/include/hft_parser', 'hftp_backend_headers', (
        'History/Archive/BasisTime.hpp',
        'History/Archive/CandleArchiveQuotaLedger.hpp',
        'History/Archive/CandleArchiveQuotaState.hpp',
        'History/CandleArchiveAcquisition.hpp',
        'History/CandleHistoryArchive.hpp',
        'History/CandleHistoryContracts.hpp',
        'History/CandleHistoryStartupPolicy.hpp',
        'History/CandleHistoryTailMerge.hpp',
        'History/CurrentHistoryFocus.hpp',
        'History/Detail/MarketHistoryAttemptBudget.hpp',
        'History/Detail/MarketHistoryQueryIdentity.hpp',
        'History/Candles/CandleBackfillPlanner.hpp',
        'History/Candles/CandleHistoryWorker.hpp',
        'History/Candles/Detail/CandleArchiveCheckpointCommitPolicy.hpp',
        'History/Candles/Detail/CandleBackfillFairness.hpp',
        'History/Candles/SelectedCandleBackfillQueue.hpp',
        'History/Catalog/ArchiveCatalog.hpp',
        'History/Catalog/ArchiveCatalogMutationFence.hpp',
        'History/Catalog/ArchiveCatalogSnapshot.hpp',
        'History/Catalog/CandleArchiveCatalogOwner.hpp',
        'History/Catalog/Detail/CandleArchiveCatalogRefreshPolicy.hpp',
        'History/FullCandleBackfillCheckpoint.hpp',
        'History/LegacyCandleHistoryArchive.hpp',
        'History/MarketHistoryIpc.hpp',
        'History/MarketHistorySource.hpp',
        'History/Metadata/InstrumentArchiveMetadataAcquisition.hpp',
        'History/Metadata/InstrumentArchiveSidecar.hpp',
        'History/SavedArchiveCatalogStore.hpp',
        'Internal/AsciiText.hpp',
        'Internal/BoundedSpscRing.hpp',
        'Internal/BorrowedArray.hpp',
        'Internal/CheckedArithmetic.hpp',
        'Internal/OwnerDiagnostic.hpp',
        'Internal/ValidateOnlySink.hpp',
        'Market/Catalog/InstrumentCatalogBootstrap.hpp',
        'Market/Catalog/InstrumentCatalogMetadataCompanion.hpp',
        'Market/Catalog/InstrumentMetadataBootstrap.hpp',
        'Market/Catalog/InstrumentUniverseCoordinator.hpp',
        'Market/Catalog/NativeOrderMetadataProvider.hpp',
        'Market/Catalog/SpotInstrumentCapabilityBootstrap.hpp',
        'Market/Catalog/UniverseSubscriptionProjection.hpp',
        'Market/Ingestion/EarlyAccountPreparation.hpp',
        'Market/Ingestion/InstrumentDenominationPlanBuilder.hpp',
        'Market/Ingestion/InstrumentSubscriptionPolicy.hpp',
        'Market/Ingestion/MarketSource.hpp',
        'Market/Ingestion/NativeMarketObserver.hpp',
        'Market/Ingestion/ParserStartupConfig.hpp',
        'Market/Ingestion/PublicMarketDepthNumeric.hpp',
        'Market/Ingestion/PublicMarketOwnerHooks.hpp',
        'Market/Ingestion/PublicMarketOwnerProgress.hpp',
        'Market/Ingestion/PublicMarketProcessRoot.hpp',
        'Market/Ingestion/PublicMarketShardPlanner.hpp',
        'Market/Ingestion/PublicMarketStartupTopology.hpp',
        'Market/MarketDemandServer.hpp',
        'Market/Planning/PublicMarketTopologyPlanner.hpp',
        'Market/PublicMarketTypes.hpp',
        'Market/Registry/InstrumentCatalogSelection.hpp',
        'Market/Registry/PublicMarket.hpp',
        'Market/Registry/PublicMarketDescriptorCatalog.hpp',
        'Market/Registry/PublicMarketOperationalPolicy.hpp',
        'Market/Registry/PublicMarketProductPolicy.hpp',
        'Market/Registry/PublicMarketRegistry.hpp',
        'Projection/Ipc/AlgosDataPlaneService.hpp',
        'Projection/Ipc/DepthProjectionBuffer.hpp',
        'Projection/Ipc/DepthSharedArenaView.hpp',
        'Projection/Ipc/DepthSharedConsumer.hpp',
        'Projection/Ipc/DepthSharedPublisher.hpp',
        'Projection/Ipc/MarketCaptureArenaView.hpp',
        'Projection/Ipc/MarketCapturePublisher.hpp',
        'Projection/Ipc/MarketSharedArenaView.hpp',
        'Projection/Ipc/MarketSharedPublisher.hpp',
        'Projection/Ipc/ReferenceProjectionCache.hpp',
        'Projection/Ipc/ReferenceSnapshotPublisher.hpp',
        'Projection/PublicMarketFenceCapture.hpp',
        'Projection/PublicProjectionDiagnosticLatch.hpp',
        'Projection/SyntheticProjectionTurnClock.hpp',
        'Reference/CentralBankDecision.hpp',
        'Reference/CentralBankDecisionStore.hpp',
        'Reference/CentralBankRateCache.hpp',
        'Reference/CentralBankRateStore.hpp',
        'Reference/DeliveryTermsStore.hpp',
        'Reference/Detail/DeliveryBasisCommitFailure.hpp',
        'Reference/Detail/CatalogTopologyPublicationBarrier.hpp',
        'Reference/Detail/FocusedInstrumentCatalogSelection.hpp',
        'Reference/Detail/InstrumentCatalogBudget.hpp',
        'Reference/Detail/InstrumentAdmissionMerge.hpp',
        'Reference/Detail/InstrumentCatalogStartupPrefix.hpp',
        'Reference/Detail/InstrumentCompanionNormalization.hpp',
        'Reference/Detail/InstrumentSpecificationPreparation.hpp',
        'Reference/Detail/NativeCatalogPreparation.hpp',
        'Reference/Detail/ReferenceFailureMapping.hpp',
        'Reference/InstrumentCatalogSession.hpp',
        'Reference/InstrumentUniverseReader.hpp',
        'Reference/ReferenceCache.hpp',
        'Reference/ReferenceRuntimeCoordinator.hpp',
        'Reference/ReferenceScheduler.hpp',
        'Reference/ReferenceSnapshotView.hpp',
        'Reference/ReferenceTypes.hpp',
        'Session/Native/NativeAccountAcquisitionFailure.hpp',
        'Session/Native/NativeAccountPublicationProducer.hpp',
        'Session/Native/NativeAccountSession.hpp',
        'Session/Native/NativeAccountStopState.hpp',
        'Session/Native/NativeColdExecutor.hpp',
        'Session/Native/NativeCurrentRunFeed.hpp',
        'Session/Native/NativeOrderBindingStore.hpp',
        'Session/Native/NativeOrderSession.hpp',
        'Session/Native/NativeProfileProducer.hpp',
        'Session/Native/NativeRecoveryWindow.hpp',
        'Session/Native/ProfileAccountIdentity.hpp',
        'Session/SessionNativeCorrelation.hpp',
        'Session/SessionService.hpp',
        'Transport/ConnectionSupervisor.hpp',
        'Transport/IoUringCapabilities.hpp',
        'Transport/TransportTypes.hpp',
    )),
    ('apps/hft-parser/src/Runtime/include/hft_parser', 'hftp_session_private_publisher', (
        'Session/Private/PrivatePublisher.hpp',
    )),
    ('apps/hft-parser/src/Process/include/hft_parser', 'hftp_backend_headers', (
        'Process/Bootstrap/ParserMarketApplication.hpp',
        'Process/Bootstrap/ParserReferenceRuntime.hpp',
        'Process/Bootstrap/ParserdStartupPolicy.hpp',
        'Process/Config/TrustedConfigFile.hpp',
        'Process/Resources/ResourcePlanner.hpp',
        'Process/Resources/ResourceTopology.hpp',
        'Process/SessiondApplication.hpp',
    )),
    ('apps/trader/alerts/include/trader', None, (
        'Alerts/AlertContext.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_client', (
        'Alerts/Client.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_telegram', (
        'Alerts/Console.hpp',
        'Alerts/Telegram.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_service', (
        'Alerts/DeliveryIdentity.hpp',
        'Alerts/ErrorReport.hpp',
        'Alerts/Journal.hpp',
        'Alerts/Server.hpp',
        'Alerts/Service.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_bridge', (
        'Alerts/HotBridge.hpp',
        'Market/Alerts/MetricValues.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_presentation', (
        'Alerts/Presentation.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_contracts', (
        'Alerts/Protocol.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_observer', (
        'Alerts/StrategyObserver.hpp',
    )),
    ('apps/trader/alerts/include/trader', 'trader_alert_evaluator', (
        'Market/Alerts/Runtime.hpp',
    )),
    ('apps/trader/src/Market/include/trader/Market', 'trader_public_analytics', (
        'Algorithms/AlgorithmCatalog.hpp',
        'Algorithms/AlgorithmConfig.hpp',
        'Algorithms/AlgorithmDescriptor.hpp',
        'Algorithms/CrossBboSpreadVolatility/Descriptor.hpp',
        'Algorithms/IntraBboSpreadVolatility/Descriptor.hpp',
        'Algorithms/StrategyParameterView.hpp',
        'Algorithms/StrategyUniverseProjection.hpp',
        'Algorithms/SymbolBucketPlanner.hpp',
        'Algorithms/SyntheticBboSpread/SyntheticBboSpreadAlgorithm.hpp',
        'Analysis/Delivery/DeliveryBasis.hpp',
        'Analysis/Delivery/SyntheticDeliveryBasis.hpp',
        'Analysis/MarketProcessorChain.hpp',
        'Analysis/Ranking/RankingCandidateAdapter.hpp',
        'Analysis/Ranking/RankingColumnProvider.hpp',
        'Analysis/Ranking/RankingColumnRegistry.hpp',
        'Analysis/Ranking/RankingEngine.hpp',
        'Analysis/Ranking/RankingMetricConnector.hpp',
        'Analysis/Ranking/RankingMetricDirectory.hpp',
        'Analysis/Ranking/RankingQueryRegistry.hpp',
        'Analysis/Ranking/SpreadRankingMetric.hpp',
        'Analysis/Volatility/SpreadVolatilityAlgorithmAdapter.hpp',
        'Analysis/Volatility/SpreadVolatilityProcessor.hpp',
        'Analysis/Bbo/SyntheticBboSpreadProcessor.hpp',
        'Analysis/Bbo/SyntheticPairSelection.hpp',
        'Analysis/Ranking/VolumeRankingMetric.hpp',
        'Analytics/ConfigFile.hpp',
        'Analytics/Pipeline.hpp',
    )),
    ('apps/trader/src/Market/include/trader/Market', 'trader_market_client', (
        'Client/Client.hpp',
        'Client/Protocol.hpp',
    )),
    ('apps/trader/src/Market/include/trader/Market', 'trader_market_observe_runtime', (
        'Observe/Runtime.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_projection_client', (
        'Client/Client.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_live_market_client', (
        'Client/LiveMarketSource.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_market_observe_projection_client', (
        'Client/MarketObserveClient.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_projection_source', (
        'Client/ProjectionSource.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_live_market_relay', (
        'Publisher/LiveMarketRelay.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_market_observe_projection_publisher', (
        'Publisher/MarketObservePublisher.hpp',
    )),
    ('apps/trader/src/Projection/include/trader/Projection', 'trader_projection_publisher', (
        'Publisher/Publisher.hpp',
        'Publisher/PublisherTypes.hpp',
    )),
    ('apps/hft-parser/src/Runtime/include/hft_parser', None, (
        'History/CandleHistoryBuild.hpp',
    )),
)

API_HEADER_OWNERS = {
    f"{root}/{name}": owner
    for root, owner, names in _PARTITION_GROUPS
    for name in names
}

PARTITIONED_HEADER_ROOTS = frozenset(
    root for root, _, _ in _PARTITION_GROUPS)

# This cold composition object intentionally joins declaration-only service,
# analytics and public-runtime types without creating a runtime link cycle.
# It is never an independently exported API seed. Access still needs the
# original compiled target's actual guaranteed CMake compiler environment.
PRIVATE_COMPOSITION_HEADER_TARGETS = {
    'apps/hft-parser/src/Runtime/include/hft_parser/History/CandleHistoryBuild.hpp': frozenset({
        'hftp_ingestion_common', 'hftp_ingestion', 'hftp_trading_ingestion',
        'hftp_runtime_common', 'hftp_parserd_runtime', 'hftp_trading_runtime', 'hftp_reference',
    }),
    'apps/trader/alerts/include/trader/Alerts/AlertContext.hpp': frozenset({
        'trader_public_analytics', 'trader_traderd_process',
        'trader_market_observe_process', 'trader_market_observe_runtime',
    }),
}

_PARSER_PUBLIC_PROCESS_HEADERS = frozenset({
    'apps/hft-parser/src/Runtime/include/hft_parser/Market/Ingestion/ParserStartupConfig.hpp',
    'apps/hft-parser/src/Process/include/hft_parser/Process/Bootstrap/ParserMarketApplication.hpp',
})
_PARSER_FULL_PROCESS_HEADERS = _PARSER_PUBLIC_PROCESS_HEADERS | {
    'apps/hft-parser/src/Runtime/include/hft_parser/Session/Native/NativeAccountSession.hpp',
    'apps/hft-parser/src/Runtime/include/hft_parser/Session/Native/NativeColdExecutor.hpp',
    'apps/hft-parser/src/Runtime/include/hft_parser/Session/Native/NativeProfileProducer.hpp',
    'apps/hft-parser/src/Runtime/include/hft_parser/Internal/OwnerDiagnostic.hpp',
}


def parser_process_include(target, source, selected):
    """Only the explicit cold process compositions may name backend headers."""
    if not source.startswith('apps/trader/src/Process/src/'):
        return False
    if target in {'traderd', 'trader_traderd_process'}:
        return selected in _PARSER_FULL_PROCESS_HEADERS
    if target in {'trader-market-observed', 'trader_market_observe_process'}:
        return selected in _PARSER_PUBLIC_PROCESS_HEADERS
    return False


def experimental_api_available(selected, providers):
    owner = API_HEADER_OWNERS.get(selected)
    return owner not in {'capital_planning'} or owner in providers


def vetron_full_api_available(selected, providers):
    """A shared include root never grants the separate Full composition."""
    owner = API_HEADER_OWNERS.get(selected)
    return owner not in {'vetron_full_control', 'vetron_full_process'} or owner in providers


def private_composition_include(target, source, selected, roots, *, public_seed):
    """An exact implementation grant never creates a public header API."""
    parser_build = selected == ('apps/hft-parser/src/Runtime/include/hft_parser/'
                                'History/CandleHistoryBuild.hpp')
    source_allowed = (source.startswith(('apps/hft-parser/src/Runtime/src/',
                                         'apps/hft-parser/src/Process/src/'))
                      if parser_build else source.startswith('apps/trader/'))
    return (not public_seed and source_allowed and
            target in PRIVATE_COMPOSITION_HEADER_TARGETS.get(selected, ()) and
            any(selected.startswith(root + '/') for root in roots))


def canonical_api_headers(physical, concrete, errors):
    """Classify all physical headers, then seed only each reviewed API owner."""
    semantic = {}
    visible = {relative for headers in physical.values() for relative in headers}
    active_roots = {root for root in PARTITIONED_HEADER_ROOTS
                    if any(relative.startswith(root + "/") for relative in visible)}
    for relative in sorted(API_HEADER_OWNERS):
        if (relative not in visible and
                any(relative.startswith(root + "/") for root in active_roots)):
            errors.append(f"reviewed API header is no longer compiler-visible: {relative}")
    for carrier, headers in physical.items():
        for relative in headers:
            partitioned = any(relative.startswith(root + "/")
                              for root in PARTITIONED_HEADER_ROOTS)
            if not partitioned:
                semantic.setdefault(carrier, set()).add(relative)
                continue
            if relative not in API_HEADER_OWNERS:
                errors.append(f"unclassified compiler-visible API header: {relative}")
                continue
            owner = API_HEADER_OWNERS[relative]
            # None is an explicitly private composition header. Offline APIs
            # remain classified even when their owner is absent from a product.
            if owner is not None and owner in concrete:
                semantic.setdefault(owner, set()).add(relative)
    return {target: tuple(sorted(headers))
            for target, headers in sorted(semantic.items())}


def finance_leaf_include(source, selected, target=None):
    """Production finance never imports execution/strategy through a shared root."""
    if target != "capital_finance" and not source.startswith("apps/trading-core/capital/"):
        return True
    production = source.startswith(("apps/trading-core/capital/src/Accounting/",
        "apps/trading-core/capital/src/Risk/")) or source.endswith(("/src/Finance.cpp", "/src/FinancialExposure.cpp",
            "/src/FinanceArithmetic.hpp"))
    owner = API_HEADER_OWNERS.get(source)
    if target != "capital_finance" and not production and owner != "capital_finance":
        return True
    if selected.startswith("apps/trading-core/src/Core/include/trading_core/"):
        return False
    return True
