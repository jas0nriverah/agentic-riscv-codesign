(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1196 (bvadd (bvshl independent_opaque_1 (bvand (_ bv24 32) (_ bv31 32))) (_ bv15 32))))
(let ((?x37 (bvand (_ bv24 32) (_ bv31 32))))
(let ((?x25 (bvadd (bvshl independent_opaque_0 (bvand (_ bv13 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x276 (bvadd (bvshl ?x25 ?x37) (_ bv15 32))))
(and (distinct ?x276 ?x1196) true))))))
(check-sat)
