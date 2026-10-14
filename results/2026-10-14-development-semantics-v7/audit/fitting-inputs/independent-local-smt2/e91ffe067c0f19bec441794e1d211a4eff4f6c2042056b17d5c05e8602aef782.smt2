(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x85 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv1114112 32))))
(let ((?x573 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x385 (bvshl (bvadd independent_opaque_0 (_ bv17 32)) ?x573)))
(and (distinct ?x385 ?x85) true)))))
(check-sat)
