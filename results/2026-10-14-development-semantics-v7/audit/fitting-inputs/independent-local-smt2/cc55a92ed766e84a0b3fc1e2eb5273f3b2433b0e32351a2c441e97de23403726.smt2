(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x82 (bvshl independent_opaque_0 (bvand (_ bv21 32) (_ bv31 32)))))
(let ((?x941 (bvadd ?x82 independent_opaque_1)))
(let ((?x983 (bvadd independent_opaque_1 ?x82)))
(and (distinct ?x983 ?x941) true)))))
(check-sat)
