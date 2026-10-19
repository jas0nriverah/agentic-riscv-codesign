(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x654 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv7 32) (_ bv31 32)))) (bvshl independent_opaque_1 (bvand (_ bv7 32) (_ bv31 32))))))
(let ((?x682 (bvand (_ bv7 32) (_ bv31 32))))
(let ((?x898 (bvshl (bvsub independent_opaque_1 independent_opaque_0) ?x682)))
(and (distinct ?x898 ?x654) true)))))
(check-sat)
