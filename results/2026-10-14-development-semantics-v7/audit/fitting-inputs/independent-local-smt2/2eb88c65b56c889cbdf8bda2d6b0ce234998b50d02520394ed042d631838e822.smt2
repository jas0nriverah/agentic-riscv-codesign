(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1103 (bvadd (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_2 (bvand (_ bv13 32) (_ bv31 32)))))))
(let ((?x1357 (bvadd independent_opaque_0 ?x1103)))
(let ((?x155 (bvand (_ bv13 32) (_ bv31 32))))
(let ((?x682 (bvsub independent_opaque_0 (bvshl (bvsub independent_opaque_2 independent_opaque_1) ?x155))))
(and (distinct ?x682 ?x1357) true))))))
(check-sat)
